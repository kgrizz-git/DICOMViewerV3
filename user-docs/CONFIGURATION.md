# Configuration and preferences

This guide describes **where** to change behavior that is saved between sessions. It complements the **[User guide hub](USER_GUIDE.md)** (workflows and features).

## Edit → Settings…

Open **Edit → Settings…** for cross-cutting preferences that are **not** under the View menu.

The dialog explains that **overlay** density and tag lists live under **View → Overlay Settings** and **View → Overlay Tags Configuration**; **annotation** defaults under **View → Annotation Options**; **privacy** under **View → Privacy Mode**.

### Local study index (encrypted)

The **Local study index (encrypted)** group stores metadata about studies you open so they can be browsed or searched locally (MVP behavior may evolve—see **Advanced** below).

| Control | Meaning |
|--------|---------|
| **Automatically add files to the study index when opened successfully** | When enabled, successfully opened files are recorded in the index. |
| **Database file** | Path to the encrypted SQLite database file. **Browse…** chooses a path; **Use default path** clears the field so the app uses its default (typically next to your app config file). |
| Hint text in the dialog | The database is encrypted with **SQLCipher**. The encryption key is stored in the **OS credential manager**, not in the JSON config file. |

**Privacy:** Indexed metadata reflects what was read from DICOM files; use **Privacy mode** when presenting the UI to others, and treat the database file as **sensitive**—protect backups accordingly.

**Advanced (design / roadmap):** [Local study database and indexing plan](../dev-docs/plans/supporting/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md) — developer-oriented background; not required for day-to-day use.

## View menu and related dialogs

Many visual and interaction options open dedicated dialogs (persisted in config). Use the **View** menu and image **right-click** menus in the running app; narrative documentation is in **[USER_GUIDE.md](USER_GUIDE.md)** (for example corner overlays, themes, layout, scroll-wheel mode).

## In-app documentation URLs (forks and releases)

**Help → Documentation** and links inside **Help → Quick Start Guide** use the GitHub base URL in `src/utils/doc_urls.py` (`USER_DOCS_GITHUB_PREFIX`). Forks or private builds should point that constant at the correct branch or tree. Release-matched doc policy is described in **[RELEASING.md](../dev-docs/RELEASING.md#in-app-user-documentation-urls)**.
