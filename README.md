# ParcelCare — Complaint Portal

Web portal for raising and tracking complaints about undelivered or missing online shopping orders.

## Features

- **File a complaint**: order details, issue type (never delivered, false delivery scan, wrong address, empty/tampered, partial) and preferred resolution. Returns a `CMP-XXXXXX` ticket.
- **Track status**: look up a ticket to see its details and a full timeline of status updates.
- **Support desk** (`/admin`): search and filter complaints, change status (Open, In Review, Refund Approved, Resolved, Rejected) and attach a customer-visible note.

## Stack

Flask + SQLite (`complaints.db` is created automatically), server-rendered Jinja templates, no build step.

## Run

```bash
pip install flask
python app.py       # http://localhost:5000
```

## Layout

```
app.py             routes, schema, business logic
templates/         home, complaint form, tracking, support desk
static/style.css   styling
```
