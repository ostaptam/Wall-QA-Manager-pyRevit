from pyrevit import revit, DB, forms

doc = revit.doc

def mm_to_feet(mm):
    return mm / 304.8

rules = {
    510: {
        "comment": "External load-bearing wall",
        "fire": "REI 120"
    },
    380: {
        "comment": "Internal load-bearing wall",
        "fire": "REI 90"
    },
    100: {
        "comment": "Partition wall",
        "fire": "EI 30"
    }
}

allowed_widths = [100, 380, 510]
tolerance = mm_to_feet(5)

def get_walls():
    return (
        DB.FilteredElementCollector(doc)
        .OfCategory(DB.BuiltInCategory.OST_Walls)
        .WhereElementIsNotElementType()
        .ToElements()
    )

def classify_walls(walls):
    updated = 0
    skipped = 0

    with revit.Transaction("Wall QA Manager - Classify Walls"):
        for wall in walls:
            wall_type = doc.GetElement(wall.GetTypeId())
            width = wall_type.Width

            matched_rule = None

            for thickness_mm in rules:
                target_width = mm_to_feet(thickness_mm)

                if abs(width - target_width) <= tolerance:
                    matched_rule = rules[thickness_mm]
                    break

            if matched_rule:
                comments_param = wall.LookupParameter("Comments")
                fire_param = wall_type.LookupParameter("Fire Rating")

                if comments_param:
                    comments_param.Set(matched_rule["comment"])

                if fire_param:
                    fire_param.Set(matched_rule["fire"])

                updated += 1
            else:
                skipped += 1

    return updated, skipped

def audit_walls(walls):
    bad_ids = []

    empty_comments = 0
    missing_fire = 0
    bad_height = 0
    bad_width = 0

    for wall in walls:
        wall_type = doc.GetElement(wall.GetTypeId())

        comments_param = wall.LookupParameter("Comments")
        if comments_param:
            comments = comments_param.AsString()
            if not comments:
                empty_comments += 1
                if wall.Id not in bad_ids:
                    bad_ids.append(wall.Id)

        height_param = wall.LookupParameter("Unconnected Height")
        if height_param:
            height = height_param.AsDouble()
            if height > mm_to_feet(3000):
                bad_height += 1
                if wall.Id not in bad_ids:
                    bad_ids.append(wall.Id)

        fire_param = wall_type.LookupParameter("Fire Rating")
        if fire_param:
            fire = fire_param.AsString()
            if not fire:
                missing_fire += 1
                if wall.Id not in bad_ids:
                    bad_ids.append(wall.Id)

        width = wall_type.Width
        valid_width = False

        for allowed in allowed_widths:
            target_width = mm_to_feet(allowed)

            if abs(width - target_width) <= tolerance:
                valid_width = True
                break

        if not valid_width:
            bad_width += 1
            if wall.Id not in bad_ids:
                bad_ids.append(wall.Id)

    if bad_ids:
        revit.get_selection().set_to(bad_ids)

    return empty_comments, missing_fire, bad_height, bad_width, bad_ids

import os
from pyrevit import script

class WallQAWindow(forms.WPFWindow):
    def __init__(self):
        xamlfile = os.path.join(script.get_bundle_file('ui.xaml'))
        forms.WPFWindow.__init__(self, xamlfile)

        self.action = None

        self.btn_classify.Click += self.classify_click
        self.btn_audit.Click += self.audit_click
        self.btn_full.Click += self.full_click

    def classify_click(self, sender, args):
        self.action = "Classify Walls"
        self.Close()

    def audit_click(self, sender, args):
        self.action = "Audit Walls"
        self.Close()

    def full_click(self, sender, args):
        self.action = "Full QA/QC"
        self.Close()

window = WallQAWindow()
window.ShowDialog()

action = window.action

if not action:
    forms.alert("Cancelled")
    script_exit = True
else:
    script_exit = False

if not script_exit:
    walls = get_walls()

    if action == "Classify Walls":
        updated, skipped = classify_walls(walls)

        forms.alert(
            "Wall Classification Report\n\n"
            + "Walls checked: " + str(len(walls)) + "\n"
            + "Updated walls: " + str(updated) + "\n"
            + "Skipped walls: " + str(skipped)
        )

    elif action == "Audit Walls":
        empty_comments, missing_fire, bad_height, bad_width, bad_ids = audit_walls(walls)

        forms.alert(
            "Wall Audit Report\n\n"
            + "Walls checked: " + str(len(walls)) + "\n\n"
            + "Empty Comments: " + str(empty_comments) + "\n"
            + "Missing Fire Rating: " + str(missing_fire) + "\n"
            + "Walls higher than 3000 mm: " + str(bad_height) + "\n"
            + "Invalid wall thickness: " + str(bad_width) + "\n\n"
            + "Problem walls selected: " + str(len(bad_ids))
        )

    elif action == "Full QA/QC":
        updated, skipped = classify_walls(walls)

        empty_comments, missing_fire, bad_height, bad_width, bad_ids = audit_walls(walls)

        forms.alert(
            "Wall QA/QC Report\n\n"
            + "Walls checked: " + str(len(walls)) + "\n\n"
            + "Classification:\n"
            + "Updated walls: " + str(updated) + "\n"
            + "Skipped walls: " + str(skipped) + "\n\n"
            + "Remaining issues:\n"
            + "Empty Comments: " + str(empty_comments) + "\n"
            + "Missing Fire Rating: " + str(missing_fire) + "\n"
            + "Walls higher than 3000 mm: " + str(bad_height) + "\n"
            + "Invalid wall thickness: " + str(bad_width) + "\n\n"
            + "Problem walls selected: " + str(len(bad_ids))
        )