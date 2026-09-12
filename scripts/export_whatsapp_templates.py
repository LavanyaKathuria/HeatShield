"""Print template bodies for submission in Twilio Content Template Builder."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.alerts.advisories import citizen_advisory
from src.alerts.render import render_whatsapp, timing_label


def templates():
    result = {}
    for language in ("en", "hi", "gu"):
        for group in ("elderly", "children", "outdoor_workers", "general"):
            for level in ("warning", "danger", "extreme"):
                advisory = citizen_advisory(group, level)
                alert = dict(language=language, group=group, level=level, ward_id="{{1}}", date="{{2}}",
                    headline_key=advisory["headline"], action_keys=advisory["actions"], why_key=advisory["why"])
                result[f"{language}.{group}.{level}"] = render_whatsapp(alert)["body"].replace(timing_label(alert), "{{3}}", 1)
    return result


if __name__ == "__main__":
    print(json.dumps(templates(), ensure_ascii=True, indent=2))
