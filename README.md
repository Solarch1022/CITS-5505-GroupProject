# SecondHand Market Platform

UWA SecondHand is a Flask-based second-hand marketplace built for the UWA campus community. The current codebase uses a traditional multi-page Flask architecture with Jinja templates for the main user flows and lightweight JavaScript for progressive enhancement such as multi-image previews, gallery controls, and chat refresh.

## Tech Stack

- Backend: Python 3.11.11 with Flask
- Database: SQLite with SQLAlchemy ORM
- Frontend: HTML5, CSS3, vanilla JavaScript, Jinja templates
- Auth and security: Flask-Login, password hashing via Werkzeug, CSRF tokens
- Deployment support: Docker and Docker Compose

## Architecture Overview

- Server-rendered pages:
  - `/` landing page
  - `/browse` and `/items` listing browser
  - `/login`
  - `/register`
  - `/sell`
  - `/item/<id>`
  - `/dashboard`
- Progressive enhancement:
  - multi-image local preview and cover-image ordering on the sell form
  - image gallery switching on item detail pages
  - inbox and item-chat polling through JSON endpoints
- API endpoints are still available under `/api/...` for auth state, listings, dashboard payloads, and conversations.

## Project Structure

```text
src/
|-- app.py                         # Flask app, routes, page rendering, APIs
|-- config.py                      # Config and DATABASE_URL resolution
|-- models.py                      # SQLAlchemy models
|-- templates/
|   |-- base.html                  # Shared layout and navigation
|   |-- index.html                 # Landing page
|   |-- login.html                 # Login page
|   |-- register.html              # Registration page
|   |-- items.html                 # Browse/search page
|   |-- sell_item.html             # Sell form
|   |-- item_detail.html           # Listing details and item chat
|   |-- dashboard.html             # User dashboard and inbox
|   `-- partials/
|       |-- item_card.html         # Reusable listing card
|       `-- reputation_badges.html # Reputation / UWA badge snippet
|-- static/
|   |-- css/
|   |   `-- style.css              # Shared styling
|   |-- js/
|   |   `-- main.js                # Image preview, gallery, and chat JS
|   `-- uploads/
|       `-- items/                 # Uploaded listing images
tests/
|-- test_app.py                    # Unit tests
test_integration.py                # Smoke test
instance/
`-- app.db                         # Local SQLite database file
```

## Current Features

- UWA-only registration using `@student.uwa.edu.au` email validation
- Login, logout, and protected routes with Flask-Login
- Browse and search listings by category and keyword
- Create listings with up to 6 local images
- Reorder selected images so any image can become the cover photo
- Display cover image in browse cards and a multi-image gallery on item detail pages
- Purchase available items and record completed transactions
- View personal listings, purchases, and sales in the dashboard
- Start buyer-seller conversations from a listing
- View and reply to item-specific and dashboard inbox conversations
- Reputation summaries based on completed trades
- CSRF protection for form posts and JSON write endpoints

## Database Schema

### Users

- `id`
- `username`
- `email`
- `password_hash`
- `full_name`
- `bio`
- `created_at`
- `updated_at`

### Items

- `id`
- `title`
- `description`
- `price`
- `category`
- `condition`
- `seller_id`
- `is_sold`
- `created_at`
- `updated_at`

### Item Images

- `id`
- `item_id`
- `file_path`
- `sort_order`
- `created_at`

### Transactions

- `id`
- `item_id`
- `seller_id`
- `buyer_id`
- `price`
- `status`
- `created_at`
- `updated_at`

### Conversations

- `id`
- `item_id`
- `seller_id`
- `buyer_id`
- `created_at`
- `updated_at`

### Messages

- `id`
- `conversation_id`
- `sender_id`
- `body`
- `created_at`

## Data Storage

- Default database file: `instance/app.db`
- Uploaded item images: `src/static/uploads/items/<item_id>/...`
- Default database URL from `.env.example`: `sqlite:///instance/app.db`

`src/config.py` resolves SQLite paths to absolute paths so the app works correctly on Windows as well as Unix-like environments.

## Environment Variables

The app reads `.env` automatically. Current variables are:

- `FLASK_ENV`
- `SECRET_KEY`
- `DATABASE_URL`
- `PORT` (optional, defaults to `8000`)

## Setup and Installation

### Prerequisites

- Python 3.11.11
- Docker and Docker Compose (optional)

### Installation

1. Create a virtual environment:

   ```bash
   python -m venv venv
   ```

2. Activate it:

   On macOS/Linux:

   ```bash
   source venv/bin/activate
   ```

   On Windows PowerShell:

   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy the environment file:

   On macOS/Linux:

   ```bash
   cp .env.example .env
   ```

   On Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

## Running the Application

### Default

```bash
python src/app.py
```

The default port is `8000`.

### Windows PowerShell example

If `8000` is already occupied on your machine:

```powershell
$env:PORT=5000
python src\app.py
```

Then open:

```text
http://localhost:5000
```

Otherwise the default URL is:

```text
http://localhost:8000
```

## Test Commands

Unit tests:

```bash
python -m unittest discover -s tests -v
```

Smoke test:

```bash
python test_integration.py
```

Current automated coverage includes:

- home page route
- browse page route
- UWA email validation
- CSRF protection on item creation
- authenticated item creation
- buyer conversation creation and messaging
- conversation access control

## Default Categories

- Electronics
- Furniture
- Clothing
- Books
- Sports
- Other

## Item Conditions

- New
- Like New
- Good
- Fair
