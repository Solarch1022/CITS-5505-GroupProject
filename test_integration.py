#!/usr/bin/env python
"""Simple smoke test for the current multi-template Flask architecture."""

from src.app import create_app


def main():
    app = create_app('testing')

    with app.test_client() as client:
        response = client.get('/')
        assert response.status_code == 200, f'Expected 200 for /, got {response.status_code}'
        body = response.get_data(as_text=True)
        assert 'UWA SecondHand' in body
        assert 'Buy, sell, and message other UWA students in one place.' in body
        print('PASS: GET / serves the home page template')

        browse = client.get('/browse')
        assert browse.status_code == 200, f'Expected 200 for /browse, got {browse.status_code}'
        print('PASS: GET /browse serves the browse template')

        constants = client.get('/api/constants')
        assert constants.status_code == 200, f'Expected 200 for /api/constants, got {constants.status_code}'
        print('PASS: GET /api/constants returns marketplace constants')

        current_user = client.get('/api/auth/current-user')
        assert current_user.status_code == 200, f'Expected 200 for /api/auth/current-user, got {current_user.status_code}'
        print('PASS: GET /api/auth/current-user returns session payload')

    print('\nSmoke test complete.')


if __name__ == '__main__':
    main()
