"""
Test suite for PWA Offline Packaging and Batch Sync Replay.
"""
import json
import urllib.request
import pytest
from atlas.storage.database import AtlasDatabase

BASE_URL = 'http://127.0.0.1:8000'

def test_pwa_manifest():
    url = f"{BASE_URL}/manifest.json"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content_type = resp.headers.get('Content-Type')
        assert 'manifest+json' in content_type
        data = json.loads(resp.read().decode('utf-8'))
        assert data['name'] == 'PLOT: The Cultural Atlas'
        assert data['short_name'] == 'PLOT'
        assert data['display'] == 'standalone'
        assert data['theme_color'] == '#FBF9F4'
        assert len(data['icons']) >= 2

def test_service_worker_headers():
    url = f"{BASE_URL}/sw.js"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content_type = resp.headers.get('Content-Type')
        assert 'javascript' in content_type
        sw_allowed = resp.headers.get('Service-Worker-Allowed')
        assert sw_allowed == '/'
        body = resp.read().decode('utf-8')
        assert 'CACHE_NAME' in body
        assert 'fetch' in body

def test_batch_sync_offline_replay():
    db = AtlasDatabase('atlas.db')
    test_salt = 'pwa_test_salt_999'
    actions = [
        {
            'type': 'cast_vote',
            'question_id': 'q_01',
            'region_key': 'WEST_EUROPE',
            'choice_letter': 'A',
            'rater_salt': test_salt
        },
        {
            'type': 'submit_calibration',
            'question_id': 'q_01',
            'predictions': {'A': 0.4, 'B': 0.3, 'C': 0.2, 'D': 0.1},
            'rater_salt': test_salt
        },
        {
            'type': 'submit_perspective',
            'question_id': 'q_01',
            'choice_letter': 'A',
            'body': 'PWA offline perspective queued and synced successfully.',
            'author_salt': test_salt,
            'author_generation': 'GEN_Z',
            'author_urbanicity': 'URBAN',
            'author_macro_region': 'WEST_EUROPE'
        }
    ]

    payload = json.dumps({
        'rater_salt': test_salt,
        'batch_id': 'test_pwa_batch_001',
        'actions': actions
    }).encode('utf-8')

    url = f"{BASE_URL}/api/sync/batch"
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode('utf-8'))
        assert res['status'] == 'ok'
        assert res['processed'] == 3

    # Verify database persistence
    with db._get_connection() as conn:
        cursor = conn.cursor()
        # Verify vote
        cursor.execute('SELECT choice_letter FROM user_votes WHERE rater_salt = ? AND question_id = ?', (test_salt, 'q_01'))
        vote_row = cursor.fetchone()
        assert vote_row is not None
        assert vote_row[0] == 'A'

        # Verify calibration
        cursor.execute('SELECT brier_score FROM calibration_guesses WHERE rater_salt = ? AND question_id = ?', (test_salt, 'q_01'))
        calib_row = cursor.fetchone()
        assert calib_row is not None

        # Verify perspective
        cursor.execute('SELECT body FROM perspectives WHERE author_salt = ? AND question_id = ?', (test_salt, 'q_01'))
        persp_row = cursor.fetchone()
        assert persp_row is not None
        assert 'PWA offline perspective' in persp_row[0]
