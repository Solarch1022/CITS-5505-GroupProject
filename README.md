# SecondHand Market Platform

UWA SecondHand is a Flask-based second-hand marketplace for the UWA campus community. The application now follows a traditional multi-page Flask architecture with Jinja templates for the main user flows and lightweight JavaScript for progressive enhancement such as image previews, gallery controls, and live chat polling.

## Tech Stack

- Backend: Python 3.11.11 with Flask
- Database: SQLite with SQLAlchemy ORM
- Frontend: HTML5, CSS3, vanilla JavaScript, Jinja templates
- Deployment: Docker and Docker Compose

## Project Structure

```text
src/
|-- app.py                # Flask application entry point
|-- config.py             # Configuration settings
|-- models.py             # Database models
|-- templates/
|   |-- base.html         # Shared layout
|   |-- index.html        # Landing page
|   |-- register.html     # User registration
|   |-- login.html        # User login
|   |-- sell_item.html    # Sell item form
|   |-- items.html        # Browse items
|   |-- item_detail.html  # Item details page
|   |-- dashboard.html    # User dashboard and inbox
|   `-- partials/         # Reusable Jinja snippets
|-- static/
|   |-- css/
|   |   `-- style.css     # Main stylesheet
|   |-- js/
|   |   `-- main.js       # Gallery, image upload, and chat enhancements
|   `-- uploads/          # Uploaded item images
tests/
|-- test_app.py           # Unit tests
test_integration.py       # Smoke test
```

## Core Features

- UWA-only registration using `@student.uwa.edu.au` email validation
- Traditional server-rendered pages for home, browse, login, register, sell, item detail, and dashboard
- Persistent listings, transactions, item images, conversations, and messages
- Multi-image uploads with a selectable cover image
- Buyer and seller inbox flows with AJAX-enhanced message refresh
- Reputation summaries based on completed trades
- CSRF protection on writes and salted password hashes

## Database Schema

### Users Table

- `id` (Integer, Primary Key)
- `username` (String, Unique)
- `email` (String, Unique)
- `password_hash` (String)
- `full_name` (String)
- `bio` (Text)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Items Table

- `id` (Integer, Primary Key)
- `title` (String)
- `description` (Text)
- `price` (Float)
- `category` (String)
- `condition` (String)
- `seller_id` (Integer, Foreign Key)
- `is_sold` (Boolean)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Item Images Table

- `id` (Integer, Primary Key)
- `item_id` (Integer, Foreign Key)
- `file_path` (String)
- `sort_order` (Integer)
- `created_at` (DateTime)

### Transactions Table

- `id` (Integer, Primary Key)
- `item_id` (Integer, Foreign Key)
- `seller_id` (Integer, Foreign Key)
- `buyer_id` (Integer, Foreign Key)
- `price` (Float)
- `status` (String)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Conversations Table

- `id` (Integer, Primary Key)
- `item_id` (Integer, Foreign Key)
- `seller_id` (Integer, Foreign Key)
- `buyer_id` (Integer, Foreign Key)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Messages Table

- `id` (Integer, Primary Key)
- `conversation_id` (Integer, Foreign Key)
- `sender_id` (Integer, Foreign Key)
- `body` (Text)
- `created_at` (DateTime)

## Setup and Installation

### Prerequisites

- Python 3.11.11
- Docker and Docker Compose (optional)

### Installation

1. Create a virtual environment:

   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:

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

   ```bash
   cp .env.example .env
   ```

   On Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

## Running the Application

```bash
python src/app.py
```

The default server port is `8000`. You can override it with the `PORT` environment variable if needed.

## Test Commands

```bash
python -m unittest discover -s tests -v
python test_integration.py
```

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
