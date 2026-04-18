# Quick Start Guide

## First-Time Setup

### 1. Open the project directory

```powershell
cd C:\Users\26247\Desktop\CITS-5505-GroupProject
```

### 2. Create a virtual environment

```powershell
py -3.11 -m venv venv
```

### 3. Activate the virtual environment

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

### 5. Create the environment file

```powershell
Copy-Item .env.example .env
```

### 6. Run the development server

Default port:

```powershell
python src\app.py
```

If port `8000` is already occupied:

```powershell
$env:PORT=5000
python src\app.py
```

### 7. Open in your browser

- Default: `http://localhost:8000`
- If you changed the port: `http://localhost:5000`

## Main Pages

- Home: `/`
- Browse listings: `/browse`
- Register: `/register`
- Login: `/login`
- Sell an item: `/sell`
- Listing detail: `/item/<id>`
- Dashboard and inbox: `/dashboard`

## Typical Usage Flow

### Create an account

1. Open `/register`
2. Use a `@student.uwa.edu.au` email
3. Submit the form
4. Login with the new account

### Post a listing

1. Open `/sell`
2. Fill in title, description, price, category, and condition
3. Upload one or more local images
4. Reorder the cover image if needed
5. Submit the listing

### Browse and contact a seller

1. Open `/browse`
2. Filter by category or search keywords
3. Open an item detail page
4. Send a message to the seller from the chat section

### View your dashboard

1. Open `/dashboard`
2. Review your listings
3. Review purchases and sales
4. Use the inbox to continue conversations

## Test Commands

```powershell
python -m unittest discover -s tests -v
python test_integration.py
```
