# SecondHand Market Platform

A simple Flask-based marketplace for buying and selling second-hand items.

## Tech Stack
- **Backend**: Python 3.11.11 with Flask
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript (vanilla)
- **Deployment**: Docker & Docker Compose

## Project Structure

```
src/
├── app.py              # Flask application entry point
├── config.py           # Configuration settings
├── models.py           # Database models (User, Item, Transaction)
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── index.html      # Home page
│   ├── register.html   # User registration
│   ├── login.html      # User login
│   ├── sell_item.html  # Sell item form
│   ├── items.html      # Browse items
│   ├── item_detail.html  # Item details page
│   └── dashboard.html  # User dashboard
└── static/             # Static files
    ├── css/
    │   └── style.css   # Main stylesheet
    └── js/
        └── main.js     # JavaScript utilities
```

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
- `condition` (String) - new, like_new, good, fair
- `seller_id` (Integer, Foreign Key)
- `is_sold` (Boolean)
- `created_at` (DateTime)
- `updated_at` (DateTime)

### Transactions Table
- `id` (Integer, Primary Key)
- `item_id` (Integer, Foreign Key)
- `seller_id` (Integer, Foreign Key)
- `buyer_id` (Integer, Foreign Key)
- `price` (Float)
- `status` (String) - pending, completed, cancelled
- `created_at` (DateTime)
- `updated_at` (DateTime)

## Setup & Installation

### Prerequisites
- Python 3.11.11 (via pyenv)
- Docker & Docker Compose

### Installation Steps

1. **Set Python version**:
   ```bash
   pyenv local 3.11.11
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

### Without Docker

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server
python src/app.py
```

Server will be available at `http://localhost:5000`

### With Docker

```bash
# Build and start containers
docker-compose up --build

# Stop containers
docker-compose down
```

## Makefile Commands

```bash
make install      # Install dependencies
make run          # Run development server
make docker-build # Build Docker images
make docker-up    # Start Docker containers
make docker-down  # Stop Docker containers
make clean        # Clean up virtual environment
make db-init      # Initialize database
make db-reset     # Reset database and seed data
```

## Features

- **User Authentication**: Register and login
- **Browse Items**: Search and filter items by category
- **Sell Items**: List items for sale
- **Purchase Items**: Buy items from other sellers
- **Dashboard**: View your listings, purchases, and sales
- **User Profiles**: View seller information

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

## Future Enhancements

- User ratings and reviews
- Image uploads
- Payment integration
- Messaging system
- Advanced search filters
- Email notifications
- Admin dashboard

## License

MIT License