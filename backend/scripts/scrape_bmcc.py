"""
BMCC Full Course Catalog Scraper (v5 - Complete)
Uses Playwright to load bmcc.catalog.cuny.edu and fetch data from the
Coursedog API using the browser's authenticated session context.

Resolved field mappings (from API diagnostic):
  COURSES:
    departments[]          -> array of {name, displayName, ...} objects
    components[]           -> array of {name, code, contactHours, instructionMode, ...}
    credits.contactHours   -> {value}
    credits.creditHours    -> {min, max}
    courseTypicallyOffered  -> "Fall, Spring"
    requisites             -> prereq/coreq data
    hegisCode              -> per-course HEGIS code
    requirementDesignation -> "Regular Liberal Arts" etc.
    longName               -> full name
  PROGRAMS:
    degreeDesignation      -> "AS - Associate in Science"
    departments[]          -> ["CIS-BMC"]
    departmentOwnership[]  -> [{deptId: "CIS-BMC", ...}]
    customFields.pXTAW     -> HTML program description (key varies)
    hegisCode              -> "5101.00"
    longName               -> "Computer Science AS"
    type                   -> "Major"
    diplomaDescription     -> "Associate in Science"
    requisites.requisitesSimple -> completion requirements
"""
import json
import re
import asyncio
from datetime import datetime, timezone
from playwright.async_api import async_playwright

CATALOG_ID = 'YiimrCscg9IpPRh0XQeo'
BASE_URL = 'https://app.coursedog.com/api/v1/cm/bmc01'
PAGE_SIZE = 1000


def strip_html(html_str):
    """Remove HTML tags and collapse whitespace."""
    if not html_str:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html_str)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_credits(credits_raw):
    """Extract credit hours as a number or range string."""
    if not isinstance(credits_raw, dict):
        return 0
    ch = credits_raw.get("creditHours", 0)
    if isinstance(ch, dict):
        mn = ch.get("min", 0)
        mx = ch.get("max", 0)
        if mn and mx and mn != mx:
            return f"{mn}-{mx}"
        return mn or mx or 0
    elif isinstance(ch, (int, float)):
        return ch
    return 0


def parse_contact_hours(credits_raw):
    """Extract contact hours from credits object."""
    if not isinstance(credits_raw, dict):
        return 0
    ch = credits_raw.get("contactHours", {})
    if isinstance(ch, dict):
        return ch.get("value", 0)
    elif isinstance(ch, (int, float)):
        return ch
    return 0


def parse_components(components_list):
    """Parse course components (lecture, lab, etc.) into structured data."""
    if not isinstance(components_list, list):
        return []
    result = []
    for comp in components_list:
        if not isinstance(comp, dict):
            continue
        result.append({
            "type": comp.get("name", comp.get("code", "")),
            "contact_hours": comp.get("contactHours", 0),
            "workload_hours": comp.get("workloadHours", 0),
            "instruction_mode": comp.get("instructionMode", ""),
        })
    return result


def parse_requisites(requisites_raw):
    """Parse prerequisite/corequisite data from the requisites field."""
    if not isinstance(requisites_raw, dict):
        return {"prerequisites": [], "corequisites": []}

    prereqs = []
    coreqs = []

    for rs in requisites_raw.get("requisitesSimple", []):
        rtype = rs.get("type", "").lower()
        name = rs.get("name", "")
        rules = rs.get("rules", [])

        course_refs = []
        for rule in rules:
            if isinstance(rule, dict):
                val = rule.get("value", {})
                if isinstance(val, dict):
                    for v in val.get("values", []):
                        if isinstance(v, str):
                            course_refs.append(v)
                        elif isinstance(v, dict) and v.get("courseCode"):
                            course_refs.append(v["courseCode"])

        entry = {"name": name, "courses": course_refs}
        if "coreq" in rtype or "concurrent" in rtype:
            coreqs.append(entry)
        elif "prereq" in rtype or "requirement" in rtype or course_refs:
            prereqs.append(entry)

    return {"prerequisites": prereqs, "corequisites": coreqs}


def parse_dept_name(departments):
    """Extract department display name from departments array."""
    if isinstance(departments, list):
        for d in departments:
            if isinstance(d, dict):
                return d.get("displayName") or d.get("name", "")
            elif isinstance(d, str):
                return d
    return ""


def find_program_description(custom_fields):
    """Find the longest HTML string in customFields — that's the program description."""
    if not isinstance(custom_fields, dict):
        return ""
    best = ""
    for key, val in custom_fields.items():
        if isinstance(val, str) and len(val) > len(best) and "<p>" in val.lower():
            best = val
    return strip_html(best)


def normalize_course_ref(value):
    """Normalize a literal course code or wildcard pattern.
    
    Examples:
        'HIS  @' -> 'HIS *' (any HIS course)
        'MMP 260' -> 'MMP 260' (specific course)
        'ITL @' -> 'ITL *' (any ITL course)
    """
    # Replace @ wildcard with *
    cleaned = value.replace("@", "*")
    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


async def fetch_json(page, url):
    return await page.evaluate("""
        async (url) => {
            const res = await fetch(url);
            if (!res.ok) return { _error: res.status };
            return await res.json();
        }
    """, url)


async def paginated_fetch(page, endpoint, params):
    all_data = []
    skip = 0
    total = None
    while True:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{endpoint}?{qs}&skip={skip}&limit={PAGE_SIZE}"
        print(f"  Fetching skip={skip}...")
        result = await fetch_json(page, url)
        if isinstance(result, dict) and "_error" in result:
            print(f"  ERROR: HTTP {result['_error']}")
            break
        if isinstance(result, dict):
            data = result.get("data", [])
            total = result.get("listLength", 0)
        elif isinstance(result, list):
            data = result
            total = len(data)
        else:
            break
        all_data.extend(data)
        print(f"  Got {len(data)} items (total so far: {len(all_data)}/{total})")
        if len(data) < PAGE_SIZE or len(all_data) >= total:
            break
        skip += PAGE_SIZE
    return all_data


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                       " (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("Navigating to BMCC Catalog (establishing session)...")
        await page.goto(
            "https://bmcc.catalog.cuny.edu/",
            wait_until="domcontentloaded",
            timeout=60000
        )
        await page.wait_for_timeout(5000)
        print("Session established.\n")

        # ================================================================
        # Phase 1: Fetch ALL courses (with full field set)
        # ================================================================
        print("--- Phase 1: Fetching all courses ---")
        # Request ALL relevant columns in one pass
        course_columns = ",".join([
            "displayName", "name", "longName", "code", "courseNumber",
            "credits", "description", "subjectCode",
            "departments", "departmentOwnership",
            "components", "requisites",
            "courseTypicallyOffered", "hegisCode",
            "requirementDesignation", "courseGroupId",
            "career", "catalogPrint", "requirementGroup"
        ])
        all_courses_raw = await paginated_fetch(
            page,
            f"{BASE_URL}/courses/search/%24filters",
            {
                "catalogId": CATALOG_ID,
                "orderBy": "code",
                "formatDependents": "true",
                "columns": course_columns
            }
        )
        print(f"  Total courses fetched: {len(all_courses_raw)}\n")

        # Build lookup + normalized course list
        group_to_code = {}
        courses = []
        for c in all_courses_raw:
            code = c.get("code", "")
            gid = c.get("courseGroupId", "")
            if not gid:
                _id = c.get("_id", "")
                if "-" in _id:
                    gid = _id.split("-")[0]

            credits_raw = c.get("credits", {})
            requisites_data = parse_requisites(c.get("requisites", {}))
            components_data = parse_components(c.get("components", []))

            courses.append({
                "code": code,
                "title": c.get("name") or c.get("displayName", ""),
                "long_name": c.get("longName", ""),
                "description": c.get("description", ""),
                "credits": parse_credits(credits_raw),
                "contact_hours": parse_contact_hours(credits_raw),
                "subject": c.get("subjectCode", ""),
                "department": parse_dept_name(c.get("departments", [])),
                "components": components_data,
                "typically_offered": c.get("courseTypicallyOffered", ""),
                "prerequisites": requisites_data["prerequisites"],
                "corequisites": requisites_data["corequisites"],
                "hegis_code": c.get("hegisCode", ""),
                "requirement_designation": c.get("requirementDesignation", ""),
            })

            if gid:
                group_to_code[gid] = code

        # ================================================================
        # Phase 1.5: Fetch Requirement Groups for Prerequisites
        # ================================================================
        print("\n--- Phase 1.5: Fetching prerequisite data (requirementGroups) ---")
        req_group_ids = list(set(c.get("requirementGroup") for c in all_courses_raw if c.get("requirementGroup")))
        print(f"  Found {len(req_group_ids)} unique requirementGroups.")
        
        if req_group_ids:
            req_group_data = {}
            batch_size = 50
            for i in range(0, len(req_group_ids), batch_size):
                batch_ids = req_group_ids[i:i+batch_size]
                batch_results = await page.evaluate("""
                    async ({baseUrl, ids}) => {
                        const results = {};
                        const promises = ids.map(async (id) => {
                            try {
                                const res = await fetch(`${baseUrl}/requirementGroups/${id}?returnFields=code,catalogDisplayName,displayName,descriptionLong`);
                                if (res.ok) {
                                    results[id] = await res.json();
                                }
                            } catch(e) {}
                        });
                        await Promise.all(promises);
                        return results;
                    }
                """, {"baseUrl": "https://app.coursedog.com/api/v1/bmc01", "ids": batch_ids})
                req_group_data.update(batch_results)
                print(f"  Fetched batch {i} to {i+len(batch_ids)}")

            for i, c in enumerate(courses):
                rgid = all_courses_raw[i].get("requirementGroup")
                if rgid and rgid in req_group_data:
                    rg = req_group_data[rgid]
                    if "data" in rg and rgid in rg["data"]:
                        data = rg["data"][rgid]
                        desc = data.get("descriptionLong") or data.get("catalogDisplayName") or data.get("displayName") or ""
                        if desc:
                            if not c["prerequisites"]:
                                c["prerequisites"] = [{"name": "Required", "courses": [], "text": desc.strip()}]
                            else:
                                c["prerequisites"].append({"name": "Additional Requirements", "courses": [], "text": desc.strip()})

        # ================================================================
        # Phase 2: Fetch ALL programs (basic list)
        # ================================================================
        print("--- Phase 2: Fetching all programs ---")
        all_programs_raw = await paginated_fetch(
            page,
            f"{BASE_URL}/programs/search/%24filters",
            {
                "catalogId": CATALOG_ID,
                "orderBy": "name",
                "formatDependents": "false",
                "columns": "name,programGroupId,programCode,degree,departmentCode,catalogDisplayName,code,departments,departmentOwnership"
            }
        )
        print(f"  Total programs fetched: {len(all_programs_raw)}\n")

        # ================================================================
        # Phase 3: Fetch program details + extract degree maps
        # ================================================================
        print("--- Phase 3: Fetching program details + requirements ---")
        programs = []
        all_course_group_ids = set()
        all_course_set_group_ids = set()
        programs_with_raw_reqs = []

        for i, prog in enumerate(all_programs_raw):
            gid = prog.get("programGroupId", "")
            code = prog.get("code", gid)
            print(f"  [{i+1}/{len(all_programs_raw)}] {code}...", end=" ", flush=True)

            detail_url = (
                f"{BASE_URL}/programs"
                f"?catalogId={CATALOG_ID}"
                f"&programGroupIds={gid}"
                f"&formatDependents=true"
                f"&includeMappedDocumentItems=true"
            )
            detail_raw = await fetch_json(page, detail_url)

            # Defaults
            catalog_name = code
            cip_code = ""
            hegis_code = ""
            degree_designation = ""
            degree_maps = []
            program_description = ""
            program_type = ""
            long_name = ""
            dept_id = ""
            diploma_desc = ""
            completion_reqs = []

            if isinstance(detail_raw, dict) and not detail_raw.get("_error"):
                for key, val in detail_raw.items():
                    if not isinstance(val, dict):
                        continue
                    catalog_name = val.get("catalogDisplayName") or val.get("name", code)
                    cip_code = val.get("cipCode", "")
                    hegis_code = val.get("hegisCode", "")
                    degree_designation = val.get("degreeDesignation", "")
                    degree_maps = val.get("degreeMaps", [])
                    program_type = val.get("type", "")
                    long_name = val.get("longName", "")
                    diploma_desc = val.get("diplomaDescription", "")

                    # Extract description from customFields
                    program_description = find_program_description(
                        val.get("customFields", {})
                    )

                    # Extract department from departmentOwnership
                    dept_own = val.get("departmentOwnership", [])
                    if isinstance(dept_own, list) and dept_own:
                        dept_id = dept_own[0].get("deptId", "")

                    # Extract completion requirements from requisites
                    reqs_simple = val.get("requisites", {}).get("requisitesSimple", [])
                    for rs in (reqs_simple or []):
                        req_name = rs.get("name", "")
                        req_type = rs.get("type", "")
                        rules_summary = []
                        for rule in rs.get("rules", []):
                            cond = rule.get("condition", "")
                            rule_val = rule.get("value", {})
                            if isinstance(rule_val, dict):
                                rule_vals = rule_val.get("values", [])
                                rules_summary.append({
                                    "condition": cond,
                                    "values": [str(v) for v in rule_vals[:5]] if rule_vals else []
                                })
                            elif isinstance(rule_val, (int, float, str)):
                                rules_summary.append({"condition": cond, "value": str(rule_val)})
                        if req_name:
                            completion_reqs.append({
                                "name": req_name,
                                "type": req_type,
                                "rules": rules_summary
                            })
                    break  # Only need the first version entry

            # Extract course/courseSet group IDs from degreeMaps
            # Values can be:
            #   - Numeric courseGroupIds like "0888491" -> need lookup
            #   - Literal course codes like "MMP 260" -> pass through
            #   - Wildcard patterns like "HIS  @" -> normalize to "HIS *"
            raw_semesters = []
            for dm in degree_maps:
                for sem in dm.get("semesters", []):
                    sem_data = {
                        "year": sem.get("year", ""),
                        "semester": sem.get("semester", ""),
                        "course_group_ids": [],     # numeric IDs to resolve
                        "literal_courses": [],       # already course codes
                        "course_set_ids": []
                    }
                    for req in sem.get("requirements", []):
                        for rs in req.get("requirementSelect", []):
                            rtype = rs.get("type", "")
                            rval = rs.get("value", "")
                            if isinstance(rval, list):
                                vals = [v for v in rval if isinstance(v, str)]
                            elif isinstance(rval, str) and rval:
                                vals = [rval]
                            else:
                                vals = []
                            for v in vals:
                                if rtype == "courses":
                                    if v.isdigit():
                                        # Numeric courseGroupId -> needs lookup
                                        sem_data["course_group_ids"].append(v)
                                        all_course_group_ids.add(v)
                                    else:
                                        # Literal course code or wildcard pattern
                                        normalized = normalize_course_ref(v)
                                        sem_data["literal_courses"].append(normalized)
                                elif rtype == "courseSets":
                                    sem_data["course_set_ids"].append(v)
                                    all_course_set_group_ids.add(v)
                    raw_semesters.append(sem_data)

            programs_with_raw_reqs.append({
                "name": catalog_name,
                "programCode": code,
                "groupId": gid,
                "degree": degree_designation,
                "diploma_description": diploma_desc,
                "department": dept_id,
                "cipCode": cip_code,
                "hegisCode": hegis_code,
                "type": program_type,
                "long_name": long_name,
                "description": program_description,
                "completion_requirements": completion_reqs,
                "raw_semesters": raw_semesters
            })
            print(f"({len(raw_semesters)} semesters)")

        # ================================================================
        # Phase 4: Batch-resolve courseGroupIds to course codes
        # ================================================================
        print(f"\n--- Phase 4: Resolving {len(all_course_group_ids)} course IDs ---")
        unresolved = all_course_group_ids - set(group_to_code.keys())
        print(f"  Already known: {len(all_course_group_ids) - len(unresolved)}")
        print(f"  Need to resolve: {len(unresolved)}")

        if unresolved:
            unresolved_list = list(unresolved)
            for chunk_start in range(0, len(unresolved_list), 100):
                chunk = unresolved_list[chunk_start:chunk_start+100]
                ids_str = ",".join(chunk)
                url = f"{BASE_URL}/courses?courseGroupIds={ids_str}&catalogId={CATALOG_ID}"
                result = await fetch_json(page, url)
                if isinstance(result, list):
                    for c in result:
                        cid = c.get("courseGroupId", "")
                        ccode = c.get("code", "")
                        if cid and ccode:
                            group_to_code[cid] = ccode
                elif isinstance(result, dict) and not result.get("_error"):
                    # Could be dict keyed by ID
                    for cid, c in result.items():
                        if isinstance(c, dict):
                            ccode = c.get("code", "")
                            cgid = c.get("courseGroupId", cid)
                            if cgid and ccode:
                                group_to_code[cgid] = ccode
                print(f"  Resolved batch {chunk_start}-{chunk_start+len(chunk)}")

        # ================================================================
        # Phase 5: Resolve courseSet group IDs
        # ================================================================
        print(f"\n--- Phase 5: Resolving {len(all_course_set_group_ids)} course sets ---")
        course_set_to_codes = {}
        if all_course_set_group_ids:
            cs_list = list(all_course_set_group_ids)
            for chunk_start in range(0, len(cs_list), 50):
                chunk = cs_list[chunk_start:chunk_start+50]
                ids_param = "&".join(f"courseSetGroupIds[]={csid}" for csid in chunk)
                url = f"{BASE_URL}/courseSets?{ids_param}&catalogId={CATALOG_ID}"
                result = await fetch_json(page, url)
                if isinstance(result, dict) and not result.get("_error"):
                    for csid, cs in result.items():
                        if not isinstance(cs, dict):
                            continue
                        cs_name = cs.get("name", cs.get("description", ""))
                        dynamic_ids = cs.get("dynamicCourseList", [])
                        cs_courses = []
                        for cg_id in dynamic_ids:
                            ccode = group_to_code.get(cg_id, "")
                            if ccode:
                                cs_courses.append(ccode)
                        course_set_to_codes[csid] = {
                            "name": cs_name,
                            "courses": cs_courses
                        }
                print(f"  Resolved batch {chunk_start}-{chunk_start+len(chunk)}")

        # ================================================================
        # Phase 6: Assemble final programs with resolved course codes
        # ================================================================
        print("\n--- Phase 6: Assembling final programs ---")
        unresolved_count = 0
        for prog in programs_with_raw_reqs:
            semesters = []
            for sem in prog["raw_semesters"]:
                resolved_courses = []
                # Resolve numeric courseGroupIds
                for cid in sem["course_group_ids"]:
                    ccode = group_to_code.get(cid)
                    if ccode:
                        resolved_courses.append(ccode)
                    else:
                        resolved_courses.append(f"UNRESOLVED:{cid}")
                        unresolved_count += 1
                # Add literal course codes (already resolved)
                resolved_courses.extend(sem["literal_courses"])

                elective_groups = []
                for csid in sem["course_set_ids"]:
                    cs_info = course_set_to_codes.get(csid, {"name": f"CourseSet:{csid}", "courses": []})
                    elective_groups.append(cs_info)

                semesters.append({
                    "year": sem["year"],
                    "semester": sem["semester"],
                    "required_courses": resolved_courses,
                    "elective_groups": elective_groups
                })

            del prog["raw_semesters"]
            prog["semesters"] = semesters
            programs.append(prog)

        if unresolved_count:
            print(f"  WARNING: {unresolved_count} course refs could not be resolved")

        # ================================================================
        # Phase 7: Write catalog
        # ================================================================
        catalog = {
            "catalog_id": CATALOG_ID,
            "institution": "Borough of Manhattan Community College",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "total_courses": len(courses),
                "total_programs": len(programs)
            },
            "courses": courses,
            "programs": programs
        }

        out_path = "bmcc-catalog.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Saved {out_path}")
        print(f"  {len(courses)} courses, {len(programs)} programs")

        # Stats
        progs_with_reqs = sum(1 for p in programs if any(s.get("required_courses") for s in p.get("semesters", [])))
        progs_with_desc = sum(1 for p in programs if p.get("description"))
        progs_with_dept = sum(1 for p in programs if p.get("department"))
        progs_with_deg = sum(1 for p in programs if p.get("degree"))
        courses_with_dept = sum(1 for c in courses if c.get("department"))
        courses_with_prereqs = sum(1 for c in courses if c.get("prerequisites"))
        courses_with_offered = sum(1 for c in courses if c.get("typically_offered"))
        courses_with_contact = sum(1 for c in courses if c.get("contact_hours"))
        courses_with_components = sum(1 for c in courses if c.get("components"))

        print(f"  Programs with degree maps: {progs_with_reqs}")
        print(f"  Programs with descriptions: {progs_with_desc}")
        print(f"  Programs with department: {progs_with_dept}")
        print(f"  Programs with degree: {progs_with_deg}")
        print(f"  Courses with department: {courses_with_dept}")
        print(f"  Courses with prerequisites: {courses_with_prereqs}")
        print(f"  Courses with offered terms: {courses_with_offered}")
        print(f"  Courses with contact hours: {courses_with_contact}")
        print(f"  Courses with components: {courses_with_components}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
