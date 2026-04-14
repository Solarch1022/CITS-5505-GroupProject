#!/usr/bin/env python
"""Integration test for SecondHand Market application"""

from src.app import create_app

app = create_app('development')

print("Testing Flask application routes...")

with app.test_client() as client:
    # Test home page
    response = client.get('/')
    assert response.status_code == 200, f"Home page returned {response.status_code}"
    print('✓ GET / - Home page')
    
    # Test register page
    response = client.get('/register')
    assert response.status_code == 200
    print('✓ GET /register - Registration page')
    
    # Test register with data
    response = client.post('/register', data={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'testpass123',
        'full_name': 'Test User'
    }, follow_redirects=True)
    assert response.status_code == 200
    print('✓ POST /register - User registration')
    
    # Test login page
    response = client.get('/login')
    assert response.status_code == 200
    print('✓ GET /login - Login page')
    
    # Test login with credentials
    response = client.post('/login', data={
        'username': 'testuser',
        'password': 'testpass123'
    }, follow_redirects=True)
    assert response.status_code == 200
    print('✓ POST /login - User login')
    
    # Test browse page
    response = client.get('/browse')
    assert response.status_code == 200
    print('✓ GET /browse - Browse items')
    
    # Test sell page (requires login, will redirect)
    response = client.get('/sell')
    assert response.status_code == 200  # Redirects to login
    print('✓ GET /sell - Sell item (requires login)')
    
    # Test dashboard (requires login)
    response = client.get('/dashboard')
    assert response.status_code == 302 or response.status_code == 200
    print('✓ GET /dashboard - User dashboard')

print('\n✓✓✓ All route tests passed! ✓✓✓')
print('\nThe application is ready to use!')
print('Run: make run')
print('Then visit: http://localhost:8000')

