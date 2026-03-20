"""Pure utility functions for ComicVault."""
import html
import os
import re
import stat
import zipfile

from config import PUB_COLOURS


def natural_sort_key(text):
    """Splits strings to sort numbers mathematically instead of alphabetically."""
    return [int(chunk) if chunk.isdigit() else chunk.lower() for chunk in re.split(r'(\d+)', text)]


def generate_comicinfo_xml(data, filepath):
    """Generate ComicInfo.xml string from metadata dict."""
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    clean_name = re.sub(r'\(.*?\)|\[.*?\]', '', base_name).strip()

    m_vol_override = re.search(r'(?i)\b(?:v|vol|volume|book|bk|tpb)\.?\s*0*(\d+)', clean_name)
    is_volume = bool(m_vol_override)
    match = re.search(r'^(.*?)\s*#\s*(\d+)', clean_name)
    if not match:
        match = re.search(r'^(.*?)\s+(\d+)\s*$', clean_name)
    local_issue = ""
    if is_volume:
        local_issue = m_vol_override.group(1)
    elif match:
        local_issue = str(int(match.group(2)))
    cv_num = str(data.get("issue_number") or "")
    final_number = local_issue if (is_volume and local_issue) else (cv_num or local_issue)

    title = html.escape(str(data.get("name") or ""))
    series = html.escape(str(data.get("volume", {}).get("name") or ""))
    desc = data.get("description") or data.get("deck") or ""
    desc = html.escape(re.sub(r'<[^>]+>', '', desc).strip())

    year, month, day = "", "", ""
    date_str = data.get("cover_date") or ""
    if date_str:
        parts = date_str.split('-')
        if len(parts) >= 1:
            year = parts[0]
        if len(parts) >= 2:
            month = parts[1]
        if len(parts) >= 3:
            day = parts[2]

    writers, pencillers, inkers, colorists, letterers, cover_artists, editors = [], [], [], [], [], [], []
    for person in data.get("person_credits", []):
        roles = person.get("role", "").lower()
        name = html.escape(person.get("name", ""))
        if not name:
            continue
        if "writer" in roles:
            writers.append(name)
        if any(r in roles for r in ["penciler", "penciller"]):
            pencillers.append(name)
        if "inker" in roles:
            inkers.append(name)
        if "colorist" in roles:
            colorists.append(name)
        if "letterer" in roles:
            letterers.append(name)
        if "cover" in roles:
            cover_artists.append(name)
        if "editor" in roles:
            editors.append(name)
        if "artist" in roles and not any(r in roles for r in
                ["penciler", "penciller", "inker", "colorist", "letterer", "cover", "editor"]):
            pencillers.append(name)

    def dedup(lst):
        return ", ".join(dict.fromkeys(lst))

    story_arcs = []
    if data.get("story_arc"):
        story_arcs.append(str(data.get("story_arc")))
    for arc in data.get("story_arc_credits", []):
        story_arcs.append(arc.get("name", ""))
    unique_arcs = []
    for a in story_arcs:
        esc = html.escape(a)
        if esc and esc not in unique_arcs:
            unique_arcs.append(esc)
    arc_str = ", ".join(unique_arcs)

    characters = [html.escape(c['name']) for c in data.get('character_credits', [])]
    teams = [html.escape(t['name']) for t in data.get('team_credits', [])]
    locations = [html.escape(l['name']) for l in data.get('location_credits', [])]

    alt_series = html.escape(str(data.get("alternate_series") or ""))
    alt_num = str(data.get("alternate_number") or "")
    alt_count = str(data.get("alternate_count") or "")

    publisher = html.escape(str(data.get("volume", {}).get("publisher", {}).get("name", "") or ""))
    imprint = html.escape(str(data.get("volume", {}).get("imprint", "") or ""))
    page_count = str(data.get("page_count") or data.get("number_of_pages") or "")
    fmt = html.escape(str(data.get("format") or ""))
    age_rating = html.escape(str(data.get("rating", {}).get("name", "") if isinstance(data.get("rating"), dict) else data.get("age_rating") or ""))
    site_url = html.escape(str(data.get("site_detail_url") or ""))

    xml = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
        f'  <Title>{title}</Title>' if title else '',
        f'  <Series>{series}</Series>' if series else '',
        f'  <Number>{final_number}</Number>' if final_number else '',
        f'  <Summary>{desc}</Summary>' if desc else '',
        f'  <Year>{year}</Year>' if year else '',
        f'  <Month>{month}</Month>' if month else '',
        f'  <Day>{day}</Day>' if day else '',
        f'  <Publisher>{publisher}</Publisher>' if publisher else '',
        f'  <Imprint>{imprint}</Imprint>' if imprint else '',
        f'  <Format>{fmt}</Format>' if fmt else '',
        f'  <AgeRating>{age_rating}</AgeRating>' if age_rating else '',
        f'  <PageCount>{page_count}</PageCount>' if page_count else '',
        f'  <Writer>{dedup(writers)}</Writer>' if writers else '',
        f'  <Penciller>{dedup(pencillers)}</Penciller>' if pencillers else '',
        f'  <Inker>{dedup(inkers)}</Inker>' if inkers else '',
        f'  <Colorist>{dedup(colorists)}</Colorist>' if colorists else '',
        f'  <Letterer>{dedup(letterers)}</Letterer>' if letterers else '',
        f'  <CoverArtist>{dedup(cover_artists)}</CoverArtist>' if cover_artists else '',
        f'  <Editor>{dedup(editors)}</Editor>' if editors else '',
        f'  <StoryArc>{arc_str}</StoryArc>' if arc_str else '',
        f'  <Characters>{dedup(characters)}</Characters>' if characters else '',
        f'  <Teams>{dedup(teams)}</Teams>' if teams else '',
        f'  <Locations>{dedup(locations)}</Locations>' if locations else '',
        f'  <AlternateSeries>{alt_series}</AlternateSeries>' if alt_series else '',
        f'  <AlternateNumber>{alt_num}</AlternateNumber>' if alt_num else '',
        f'  <AlternateCount>{alt_count}</AlternateCount>' if alt_count else '',
        f'  <Web>{site_url}</Web>' if site_url else '',
        '  <PlayCount>1</PlayCount>',
        '</ComicInfo>'
    ]
    return "\n".join(filter(None, xml))


def inject_metadata_into_cbz(filepath: str, xml_string: str) -> None:
    """Append or replace ComicInfo.xml inside a CBZ file. Raises on failure."""
    with zipfile.ZipFile(filepath, 'r') as zin:
        has_xml = any(f.lower() == 'comicinfo.xml' for f in zin.namelist())

    if not has_xml:
        with zipfile.ZipFile(filepath, 'a', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('ComicInfo.xml', xml_string.encode('utf-8'))
        return

    temp_path = filepath + ".tmp"
    try:
        with zipfile.ZipFile(filepath, 'r') as zin, \
             zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename.lower() != 'comicinfo.xml':
                    zout.writestr(item, zin.read(item.filename))
            zout.writestr('ComicInfo.xml', xml_string.encode('utf-8'))
        os.replace(temp_path, filepath)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def _the_variants(series: str) -> list:
    """Return search queries to try for series names that may have a leading 'The'."""
    s = series.strip()
    if re.match(r'(?i)^the\s+', s):
        return [s, re.sub(r'(?i)^the\s+', '', s).strip()]
    else:
        return [s, f"The {s}"]


def _norm_vol_name(s: str) -> str:
    """Normalise a volume name for fuzzy matching."""
    s = re.sub(r'[:–—_-]', ' ', s.lower())
    s = re.sub(r'^the\s+', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def _score_volume(vol: dict, series_name: str, issue_num: str, year_str: str,
                 subtitle: str = "", vol_num: str = "") -> int:
    """Score a Comic Vine volume result so the best match sorts first."""
    score = 0
    vol_name_raw = str(vol.get('name') or '').lower().strip()
    want_name_raw = series_name.lower().strip()
    want_sub_raw = subtitle.lower().strip()

    vol_name_n = _norm_vol_name(vol_name_raw)
    want_name_n = _norm_vol_name(want_name_raw)
    want_sub_n = _norm_vol_name(want_sub_raw)

    if want_sub_n and f"{want_name_n} {want_sub_n}" in vol_name_n:
        score += 60
    elif want_sub_n and want_sub_n in vol_name_n:
        score += 20

    if vol_name_n == want_name_n:
        score += 50
    elif vol_name_raw == want_name_raw:
        score += 50
    elif want_name_n and want_name_n in vol_name_n:
        score += 25
    elif want_name_raw and want_name_raw in vol_name_raw:
        score += 20
    elif want_name_n and vol_name_n in want_name_n:
        score += 10

    count = int(vol.get('count_of_issues') or 0)
    if issue_num:
        try:
            if count >= int(issue_num):
                score += 30
        except ValueError:
            pass
    elif vol_num:
        try:
            if count >= int(vol_num):
                score += 15
        except ValueError:
            pass

    if year_str:
        try:
            iy = int(year_str)
            sy = int(vol.get('start_year') or 0)
            if sy > 0 and sy <= iy:
                gap = iy - sy
                if gap <= 2:
                    score += 30
                elif gap <= 5:
                    score += 22
                elif gap <= 10:
                    score += 15
                elif gap <= 20:
                    score += 8
        except (ValueError, TypeError):
            pass

    if vol_num:
        vol_name_n_check = _norm_vol_name(vol_name_raw)
        if 'deluxe' in vol_name_n_check or 'omnibus' in vol_name_n_check:
            score += 35
        elif re.search(r'\bbook\b', vol_name_n_check):
            score += 20

    score += min(10, count // 20)

    publisher = str((vol.get('publisher') or {}).get('name') or '').lower()
    english_publishers = {'dc comics', 'marvel comics', 'image comics',
                          'dark horse comics', 'idw publishing', 'boom! studios',
                          'dynamite entertainment', 'valiant', 'vertigo', 'wildstorm',
                          'aftershock comics', 'oni press'}
    if any(ep in publisher for ep in english_publishers):
        score += 25
    elif publisher and any(c in publisher for c in ('edicion', 'panini', 'planeta',
                                                     'glenat', 'urban', 'semic',
                                                     'ehapa', 'dino', 'mg publishing')):
        score -= 40

    return score


def parse_comic_filename_full(base_name: str) -> dict:
    """Parse any comic filename into structured fields."""
    year_match = re.search(r'\((\d{4})\)', base_name)
    year = year_match.group(1) if year_match else ""

    if not year:
        m_bare_year = re.search(r'\b(19|20)(\d{2})-\d{2}', base_name)
        if m_bare_year:
            year = m_bare_year.group(1) + m_bare_year.group(2)

    edition_hint = ""
    bracket_issue = ""
    for bracket in re.findall(r'\(([^)]+)\)', base_name):
        bl = bracket.lower().strip()
        if 'omnibus' in bl:
            edition_hint = 'omnibus'
        elif 'deluxe' in bl:
            edition_hint = 'deluxe'
        if not bracket_issue:
            m_bi = re.match(r'^[_#]?\s*(\d{1,4})\s*$', bl)
            if m_bi and len(m_bi.group(1)) <= 3:
                bracket_issue = str(int(m_bi.group(1)))

    clean = re.sub(r'\(.*?\)|\[.*?\]', '', base_name).strip()
    clean = re.sub(r'[\s\-_]+$', '', clean).strip()
    clean = re.sub(r'_', ' ', clean)
    clean = re.sub(r' {2,}', ' ', clean).strip()
    clean = re.sub(r'[\s\-]+$', '', clean).strip()
    clean = re.sub(r'^(0\d*|\d{1,2})[\.\-\s]+', '', clean).strip()
    clean = re.sub(r',?\s*(19|20)\d{2}-\d{2}(-\d{2})?', '', clean).strip()
    clean = re.sub(r'[,\s]+$', '', clean).strip()
    clean = re.sub(r'\s+[A-Ca-c]\s+stor(?:y|ies)\b.*$', '', clean, flags=re.I).strip()
    clean = re.sub(r'\s+(19|20)\d{2}\s*$', '', clean).strip()

    m_issue = re.search(r'^(.*?)\s*#\s*(\d+)', clean)
    if m_issue:
        series = re.sub(r'\s+(?:v|vol|volume)\.?\s*\d+$', '',
                        m_issue.group(1).strip(), flags=re.I).strip()
        return dict(series=series, vol_num="", issue=str(int(m_issue.group(2))),
                    subtitle="", year=year, is_tpb=False)

    m_vol = re.search(r'(?i)(?<!\w)(?:v|vol|volume|book|bk)\.?\s*0*(\d+)\b', clean)
    if m_vol:
        series = clean[:m_vol.start()].strip().rstrip('-\u2013\u2014 \t')
        vol_num = m_vol.group(1)
        after = clean[m_vol.end():].strip()
        m_sub = re.match(r'^[-\u2013\u2014:]\s*(.+)', after)
        subtitle = m_sub.group(1).strip() if m_sub else ""
        if not subtitle:
            if edition_hint:
                subtitle = edition_hint
            elif re.match(r'(?i)book', m_vol.group(0).strip()):
                subtitle = f"Book {vol_num}"
        return dict(series=series, vol_num=vol_num, issue="",
                    subtitle=subtitle, year=year, is_tpb=True)

    m_tpb = re.search(
        r'(?i)\b(tpb|trade\s+paperback|graphic\s+novel|omnibus|compendium|deluxe)\b', clean)
    if m_tpb:
        series = clean[:m_tpb.start()].strip().rstrip('-\u2013\u2014 ')
        subtitle = clean[m_tpb.end():].strip().lstrip('-\u2013\u2014 ')
        return dict(series=series, vol_num="", issue="",
                    subtitle=subtitle, year=year, is_tpb=True)

    m_oneshot = re.search(r'(?i)\bone-?shot\b', clean)
    if m_oneshot:
        without = (clean[:m_oneshot.start()] + clean[m_oneshot.end():]).strip().rstrip('-\u2013\u2014 ')
        m_trail = re.search(r'^(.*?)\s+0*(\d+)\s*$', without)
        if m_trail and m_trail.group(1).strip():
            series = m_trail.group(1).strip()
        else:
            series = without
        return dict(series=series, vol_num="", issue="1", subtitle="", year=year, is_tpb=False)

    m_dash = re.search(r'\s+[-\u2013\u2014]\s+', clean)
    if m_dash:
        left = clean[:m_dash.start()].strip()
        right = clean[m_dash.end():].strip()

        m_left_num = re.search(r'^(.*?)\s+0*(\d+)\s*$', left)
        if m_left_num and m_left_num.group(1).strip():
            subtitle = re.sub(r'\s+(19|20)\d{2}\s*$', '', right).strip()
            return dict(series=m_left_num.group(1).strip(), vol_num="",
                        issue=str(int(m_left_num.group(2))), subtitle=subtitle,
                        year=year, is_tpb=False)

        if not re.match(r'^\d+\s*$', right):
            m_right_num = re.search(r'^(.*?)\s+0*(\d+)\s*$', right)
            if m_right_num and m_right_num.group(1).strip():
                full_series = f"{left} - {m_right_num.group(1).strip()}".strip()
                return dict(series=full_series, vol_num="",
                            issue=str(int(m_right_num.group(2))),
                            subtitle="", year=year, is_tpb=False)
            return dict(series=left, vol_num="", issue="",
                        subtitle=right, year=year, is_tpb=True)

    m_end = re.search(r'^(.*?)\s+0*(\d+)\s*$', clean)
    if m_end and m_end.group(1).strip() and not re.match(r'^\d+$', m_end.group(1).strip()):
        return dict(series=m_end.group(1).strip(), vol_num="", issue=str(int(m_end.group(2))),
                    subtitle="", year=year, is_tpb=False)

    if bracket_issue:
        return dict(series=clean, vol_num="", issue=bracket_issue,
                    subtitle="", year=year, is_tpb=False)

    return dict(series=clean, vol_num="", issue="", subtitle="", year=year, is_tpb=False)


def parse_comic_filename(path: str) -> dict:
    """Return {'series', 'issue', 'year', 'display'} parsed from a file path."""
    base_name = os.path.splitext(os.path.basename(path))[0]
    y_match = re.search(r'\((\d{4})\)', base_name)
    year = y_match.group(1) if y_match else ""
    clean_name = re.sub(r'\(.*?\)|\[.*?\]', '', base_name).strip()
    match = re.search(r'^(.*?)\s*#\s*(\d+)', clean_name) or \
            re.search(r'^(.*?)\s+(\d+)\s*$', clean_name)
    series = match.group(1).strip() if match else clean_name
    series = re.sub(r'\s+(?:v|vol|volume)\.?\s*\d+$', '', series, flags=re.IGNORECASE).strip()
    issue = str(int(match.group(2))) if match else ""
    display = f"{series} #{issue}" + (f" ({year})" if year else "")
    return {"series": series, "issue": issue, "year": year, "display": display}


def _gc_first_article(html: str) -> str:
    """Return the first real article URL from GetComics HTML."""
    SKIP = {"?", "search", "tag", "category", "cat", "page", "wp-content",
            "cdn.", "#", "feed", "wp-json", "xmlrpc", "author", "about",
            "contact", "support", "sitemap", "privacy", "dmca", "discord",
            "readcomics", "juicychat", "craveu"}
    for m in re.finditer(r'href="((?:https?://getcomics\\.org)?/[^"]+)"', html):
        raw = m.group(1)
        url = raw if raw.startswith("http") else f"https://getcomics.org{raw}"
        if "getcomics.org" not in url:
            continue
        path = url.replace("https://getcomics.org", "").strip("/")
        segments = [s for s in path.split("/") if s]
        if len(segments) != 2:
            continue
        if any(s in SKIP for s in segments):
            continue
        if len(segments[1]) > 5:
            return url
    return ""


def force_remove_readonly(func, path, exc_info):
    """Clears the readonly bit on a file and reattempts the removal."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def pub_info(pub_raw):
    """Return (display_name, header_bg, header_fg, border_colour)."""
    pl = (pub_raw or "").lower()
    for key, (bg, fg, border) in PUB_COLOURS.items():
        if key in pl:
            return pub_raw, bg, fg, border
    return pub_raw or "Other", "#44475a", "#f8f8f2", "#6272a4"
