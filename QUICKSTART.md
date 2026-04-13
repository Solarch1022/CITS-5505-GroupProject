# Quick Start Guide

## First Time Setup (5 minutes)

### 1. Prerequisites
- Python 3.11.11 installed via `pyenv`
- Terminal/Command line access

### 2. Clone Repository
```bash
cd CITS-5505-GroupProject
```

### 3. Install Dependencies
```bash
make install
```

### 4. Initialize Database
```bash
make db-init
```

### 5. Run Development Server
```bash
make run
```

### 6. Open in Browser
Visit: `http://localhost:8000`

---

## Usage

### Create an Account
1. Click "Sign Up" on home page
2. Fill in: Full Name, Username, Email, Password
3. Click "Register"

### List an Item for Sale
1. Login to your account
2. Click "Sell" in navigation
3. Fill in: Title, Description, Price, Condition, Category
4. Click "List Item"

### Browse Items
1. Click "Browse" in navigation
2. Optionally filter by category or search
3. Click on item to view details
4. Click "Purchase Now" to buy

### View Dashboard
1. Click "Dashboard" in navigation
2. See your listings, purchases, and sales

---

## Common Commands

```bash
# Start development server
make run

# Stop server
Ctrl + C

# Reset database
make db-reset

# Using Docker (if installed)
make docker-up
make docker-down
```

---

## Testing the API

After server starts, try these URLs:

- Home: `http://localhost:8000/`
- Browse: `http://localhost:8000/browse`
- Login: `http://localhost:8000/login`
- Register: `http://localhost:8000/register`

---

## File Locations

- Backend code: `src/app.py`
- Database models: `src/models.py`
- Configuration: `src/config.py`
- HTML templates: `src/templates/`
- CSS styling: `src/static/css/style.css`
- JavaScript: `src/static/js/main.js`

---

## Troubleshooting

**Issue: "Port 5000 already in use"**
- Kill existing process: `lsof -ti:5000 | xargs kill -9`
- Or use different port in app.py

**Issue: Virtual environment not activating**
- Try: `source venv/bin/activate`
- On Windows: `venv\Scripts\activate`

**Issue: Database errors**
- Reset: `make db-reset`
- This deletes existing data and creates fresh tables

**Issue: "Python not found"**
- Set version: `pyenv local 3.11.11`
- Verify: `python --version`

---

## Next Steps

1. Read [SETUP.md](SETUP.md) for detailed configuration
2. Check [README.md](README.md) for full documentation
3. Explore code in `src/` directory
4. Start developing!

---

## Need Help?

- Check SETUP.md for detailed troubleshooting
- Review inline code comments
- Check git commit history for changes
- Ask team members on Slack
