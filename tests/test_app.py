import unittest

from src.app import create_app
from models import Conversation, Item, Message, User, db


class MarketplaceAppTestCase(unittest.TestCase):
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

    def register_user(self, username, email, password='testpass123', full_name='Test User'):
        csrf_token = self.get_csrf_token()
        return self.post_json('/api/auth/register', {
            'username': username,
            'email': email,
            'password': password,
            'full_name': full_name,
        }, csrf_token=csrf_token)

    def login_user(self, username, password='testpass123'):
        csrf_token = self.get_csrf_token()
        return self.post_json('/api/auth/login', {
            'username': username,
            'password': password,
        }, csrf_token=csrf_token)

    def create_user(self, username, email, full_name='Test User'):
        user = User(username=username, email=email, full_name=full_name)
        user.set_password('testpass123')
        db.session.add(user)
        db.session.commit()
        return user

    def test_root_route_serves_spa_shell(self):
        response = self.client.get('/')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('UWA SecondHand', body)

    def test_register_rejects_non_uwa_email(self):
        response = self.register_user('outsider', 'outsider@gmail.com')
        data = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertIn('@student.uwa.edu.au', data['error'])

    def test_register_accepts_uwa_student_email(self):
        response = self.register_user('uwauser', 'uwauser@student.uwa.edu.au')
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertTrue(data['user']['is_uwa_verified'])

    def test_create_item_requires_csrf_token(self):
        self.register_user('seller', 'seller@student.uwa.edu.au')
        self.login_user('seller')

        response = self.client.post('/api/items', json={
            'title': 'Desk Lamp',
            'description': 'Bright LED lamp for study desks on campus.',
            'price': 15,
            'category': 'Electronics',
            'condition': 'Good',
        })
        data = response.get_json()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(data['success'])

    def test_authenticated_user_can_create_item(self):
        self.register_user('seller', 'seller@student.uwa.edu.au')
        self.login_user('seller')
        csrf_token = self.get_csrf_token()

        response = self.post_json('/api/items', {
            'title': 'Desk Lamp',
            'description': 'Bright LED lamp for study desks on campus.',
            'price': 15,
            'category': 'Electronics',
            'condition': 'Good',
        }, csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['item']['title'], 'Desk Lamp')

    def test_buyer_can_start_conversation_and_send_message(self):
        with self.app.app_context():
            seller = self.create_user('seller', 'seller@student.uwa.edu.au', full_name='Seller User')
            buyer = self.create_user('buyer', 'buyer@student.uwa.edu.au', full_name='Buyer User')
            item = Item(
                title='Mini Fridge',
                description='Working mini fridge suitable for dorm rooms.',
                price=120,
                category='Electronics',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        self.login_user('buyer')
        csrf_token = self.get_csrf_token()

        start_response = self.post_json(f'/api/items/{item_id}/conversations', {
            'message': 'Hi, can I inspect this on campus tomorrow?',
        }, csrf_token=csrf_token)
        start_data = start_response.get_json()

        self.assertEqual(start_response.status_code, 200)
        self.assertTrue(start_data['success'])
        self.assertEqual(start_data['conversation']['message_count'], 1)

        conversation_id = start_data['conversation']['id']
        send_response = self.post_json(f'/api/conversations/{conversation_id}/messages', {
            'message': 'I am free after 3pm.',
        }, csrf_token=csrf_token)
        send_data = send_response.get_json()

        self.assertEqual(send_response.status_code, 201)
        self.assertTrue(send_data['success'])
        self.assertEqual(len(send_data['conversation']['messages']), 2)

    def test_conversation_access_is_restricted_to_participants(self):
        with self.app.app_context():
            seller = self.create_user('seller', 'seller@student.uwa.edu.au')
            buyer = self.create_user('buyer', 'buyer@student.uwa.edu.au')
            outsider = self.create_user('outsider', 'outsider@student.uwa.edu.au')
            item = Item(
                title='Bike',
                description='Second-hand bike in rideable condition.',
                price=90,
                category='Sports',
                condition='Fair',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.flush()

            conversation = Conversation(item_id=item.id, seller_id=seller.id, buyer_id=buyer.id)
            db.session.add(conversation)
            db.session.flush()
            db.session.add(Message(conversation_id=conversation.id, sender_id=buyer.id, body='Is this still available?'))
            db.session.commit()

            conversation_id = conversation.id
            outsider_username = outsider.username

        self.login_user(outsider_username)
        response = self.client.get(f'/api/conversations/{conversation_id}')
        data = response.get_json()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(data['success'])


if __name__ == '__main__':
    unittest.main()
