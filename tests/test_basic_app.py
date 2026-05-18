import unittest

from src.app import create_app
from models import User, db


class BasicAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def get_csrf_token(self):
        self.client.get('/')
        with self.client.session_transaction() as session:
            return session['csrf_token']

    def post_json(self, url, payload, csrf_token=None):
        headers = {}
        if csrf_token:
            headers['X-CSRF-Token'] = csrf_token
        return self.client.post(url, json=payload, headers=headers)

    def test_home_page_loads(self):
        response = self.client.get('/')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('UWA SecondHand', body)
        self.assertIn('Marketplace statistics', body)
        self.assertIn('Browse by category', body)

    def test_browse_page_loads(self):
        response = self.client.get('/items')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Browse listings', body)

    def test_public_items_api_returns_json(self):
        response = self.client.get('/api/items')
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertIn('items', data)
        self.assertIn('total', data)

    def test_register_rejects_non_uwa_email(self):
        csrf_token = self.get_csrf_token()

        response = self.post_json('/api/auth/register', {
            'username': 'outsider',
            'email': 'outsider@gmail.com',
            'password': 'TestPass@123',
            'full_name': 'Outside User',
        }, csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertIn('@student.uwa.edu.au', data['error'])

    def test_register_accepts_uwa_email_and_hashes_password(self):
        csrf_token = self.get_csrf_token()

        response = self.post_json('/api/auth/register', {
            'username': 'uwauser',
            'email': 'uwauser@student.uwa.edu.au',
            'password': 'TestPass@123',
            'full_name': 'UWA User',
        }, csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertTrue(data['email_verification_required'])

        with self.app.app_context():
            user = User.query.filter_by(username='uwauser').first()
            self.assertIsNotNone(user)
            self.assertNotEqual(user.password_hash, 'TestPass@123')
            self.assertTrue(user.check_password('TestPass@123'))
            self.assertFalse(user.email_verified)


if __name__ == '__main__':
    unittest.main()
