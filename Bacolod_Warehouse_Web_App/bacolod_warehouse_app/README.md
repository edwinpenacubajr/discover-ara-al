# Bacolod Warehouse Monitoring

## Installation
1. Install Python 3.11+.
2. Open this folder in VS Code, then open Terminal.
3. Run `python -m pip install -r requirements.txt`.
4. Run `python -m streamlit run app.py`.
5. Upload an Excel or CSV export of your original Google Sheet.

## How it works
- Original sheet columns: Trx Date, DR No., From W/H, Ship To, Status, Received Date / Memo, Memo.
- Manila air: 2–4 calendar days; Manila sea: 15–20; Cebu: 2–4.
- If Manila shipment method cannot be identified from Memo, select it in the editable table.
- The maximum lead time defines the overdue threshold. A record is overdue only if not received.
- Data is held in the Streamlit session; use Download CSV to preserve your changes. Refreshing or restarting may lose unsaved edits.
- This is a file-based dashboard, not an automatic Google Sheets sync or background notification service.
