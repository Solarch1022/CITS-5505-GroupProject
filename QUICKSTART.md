# Quick Start Guide

## First Time Setup

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
