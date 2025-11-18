# Roles Rename Helper

This project was mass-updated so that role names become:

- `casual` (previously `tutor`)
- `unit coordinator` (previously `lecturer`)
- `hr` (unchanged)

## IMPORTANT: Update database groups once

If your Django app uses `auth.Group` for roles, please run the following **one-time** command
from the project root to rename/merge groups in the database while keeping all members & permissions:

```bash
python manage.py shell < SCRIPTS/rename_groups_shell.py
```

This will:
- Ensure groups `casual`, `unit coordinator`, and `hr` exist.
- Migrate users/permissions from old groups (`tutor`, `Tutor`, `lecturer`, `Lecturer`, etc.) into the new names.
- Delete the old groups after merging.

## If you also store a `role` field on a model
The helper tries to find and update any model instances that have a `role` attribute set to `tutor` or `lecturer`,
replacing them with `casual` and `unit coordinator` respectively. If you prefer to do this with a migration, you can
adapt the same mapping into a data migration.

## Notes
- This code only changes **whole-word** occurrences of `tutor` and `lecturer` in text files. Identifiers like `TutorForm`
  or `lecturer_id` were left untouched to avoid breaking code. You can adjust manually if desired.
- UI labels are now the plain strings above. If your UI wants title-cased display (e.g. `Casual`, `Unit Coordinator`),
  consider mapping values to labels in the frontend constants.
