# Virtual Analyst Excel Add-in (VA-P5-02)

Minimal Office.js task pane add-in for Excel. Connects to the Virtual Analyst API to **pull** model data into the workbook and **push** changes back.

## Setup

1. Serve the add-in over HTTPS (required by Office). Options:
   - Use the web app: copy `taskpane.html`, `taskpane.js`, `commands.html` into `apps/web/public/excel-addin/` and ensure the web app is served at `https://localhost:3000` (or update URLs in `manifest.xml`).
   - Or run a static server from this directory with HTTPS (e.g. `npx serve -s . --listen 3000` with a cert).

2. **Sideload the add-in in Excel**:
   - Excel on Windows: File → Office Account → Manage Add-ins → Upload My Add-in → select `manifest.xml`.
   - Excel on Mac: Insert → Add-ins → My Add-ins → Upload My Add-in → select `manifest.xml`.
   - Or use [centralized deployment](https://learn.microsoft.com/en-us/office/dev/add-ins/publish/centralized-deployment) in the admin center.

3. In the task pane, set:
   - **API base URL**: e.g. `https://localhost:8000/api/v1` (or your deployed API).
   - **Tenant ID**: Your `X-Tenant-ID` header value.
   - **Connection ID**: An Excel connection ID from `GET /api/v1/excel/connections` (e.g. `ex_xxxx`).

4. **Pull**: Fetches current values for all bindings from the run and logs the sync event. (Writing values into cells by named range requires additional logic in `taskpane.js` using `Excel.run`.)

5. **Push**: Sends changes to the API (currently sends an empty `changes` array; extend the UI to collect cell changes and map to binding IDs).

## API

- `GET /api/v1/runs/{run_id}/export/excel` — download run as .xlsx (IS/BS/CF/KPIs).
- `POST/GET/PATCH/DELETE /api/v1/excel/connections` — manage connections.
- `POST /api/v1/excel/connections/{id}/pull` — get current values for bindings.
- `POST /api/v1/excel/connections/{id}/push` — send changed values.

## Manifest

`manifest.xml` references `https://localhost:3000` for the task pane and icons. Replace with your hosted URL when deploying.
