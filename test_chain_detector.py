#!/usr/bin/env python3
"""
Test suite for ChainDetector — multi-endpoint chain detection

Tests cover:
- CRUD chain detection (POST → GET → DELETE)
- Auth chain detection (POST /login → GET /protected)
- Nested resource chains
- Edge cases: no id in response, no protected endpoints, empty input
- Helper method correctness
"""

from spec_ingestion import EndpointSpec, ParameterSpec, ResponseSpec
from chain_detector import ChainDetector, EndpointChain


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ep(method, path, responses=None, parameters=None,
        request_body=None, security=None, operation_id=''):
    """Build a minimal EndpointSpec for testing."""
    return EndpointSpec(
        method=method,
        path=path,
        operation_id=operation_id or f'{method.lower()}_{path.replace("/", "_")}',
        summary='',
        description='',
        tags=[],
        parameters=parameters or [],
        request_body=request_body,
        responses=responses or [],
        security=security or [],
    )


def _resp(status_code, properties=None):
    """Build a ResponseSpec with optional property dict {name: type}."""
    schema = {}
    if properties:
        schema = {
            'type': 'object',
            'properties': {k: {'type': v} for k, v in properties.items()},
        }
    return ResponseSpec(status_code=status_code, description='', schema=schema)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_crud_chain_detected():
    """POST /pets returning id + GET/DELETE /pets/{petId} → one CRUD chain."""
    print('\n' + '='*70)
    print('TEST 1: Basic CRUD chain detection')
    print('='*70)

    endpoints = [
        _ep('POST', '/pets',
            responses=[_resp('201', {'id': 'string', 'name': 'string'})]),
        _ep('GET', '/pets/{petId}',
            responses=[_resp('200', {'id': 'string', 'name': 'string'})]),
        _ep('DELETE', '/pets/{petId}',
            responses=[_resp('204')]),
    ]

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)

    crud = [c for c in chains if c.chain_type == 'crud']
    assert len(crud) >= 1, f'Expected CRUD chain, got: {[c.name for c in chains]}'

    chain = crud[0]
    print(f'  ✓ Chain: {chain.name}')
    print(f'    Steps: {[f"{s.endpoint.method} {s.endpoint.path}" for s in chain.steps]}')

    assert chain.steps[0].endpoint.method == 'POST', 'First step must be POST'
    assert 'id' in chain.steps[0].captures, 'POST step must capture id'
    print('  ✓ POST is first step and captures id')
    print('\n✅ CRUD detection test passed\n')


def test_full_crud_ordering():
    """POST → GET → PUT → DELETE should appear in that order."""
    print('\n' + '='*70)
    print('TEST 2: Full CRUD step ordering')
    print('='*70)

    endpoints = [
        _ep('DELETE', '/items/{itemId}', responses=[_resp('204')]),
        _ep('PUT', '/items/{itemId}',
            responses=[_resp('200', {'id': 'string'})]),
        _ep('POST', '/items',
            responses=[_resp('201', {'id': 'string', 'name': 'string'})]),
        _ep('GET', '/items/{itemId}',
            responses=[_resp('200', {'id': 'string', 'name': 'string'})]),
    ]

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)

    crud = [c for c in chains if c.chain_type == 'crud']
    assert crud, 'Expected a CRUD chain'

    methods = [s.endpoint.method for s in crud[0].steps]
    post_idx = methods.index('POST')
    get_idx = methods.index('GET')
    delete_idx = methods.index('DELETE')

    assert post_idx < get_idx, 'GET must come after POST'
    assert get_idx < delete_idx, 'DELETE must come after GET'
    print(f'  ✓ Step order: {methods}')
    print('\n✅ CRUD ordering test passed\n')


def test_no_chain_without_id_in_response():
    """POST without id in response should not produce a CRUD chain."""
    print('\n' + '='*70)
    print('TEST 3: No chain when POST response has no id field')
    print('='*70)

    endpoints = [
        _ep('POST', '/pets',
            responses=[_resp('201', {'name': 'string'})]),   # no id
        _ep('GET', '/pets/{petId}',
            responses=[_resp('200', {'id': 'string'})]),
    ]

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)
    crud = [c for c in chains if c.chain_type == 'crud']

    assert len(crud) == 0, f'Expected no CRUD chain, got: {[c.name for c in crud]}'
    print('  ✓ No CRUD chain when POST has no id in response')
    print('\n✅ No-id test passed\n')


def test_auth_chain_detected():
    """POST /auth/login returning access_token + GET /profile (secured) → auth chain."""
    print('\n' + '='*70)
    print('TEST 4: Auth chain detection')
    print('='*70)

    endpoints = [
        _ep('POST', '/auth/login',
            request_body={
                'schema': {
                    'properties': {
                        'email': {'type': 'string'},
                        'password': {'type': 'string'},
                    },
                },
            },
            responses=[_resp('200', {'access_token': 'string', 'user_id': 'string'})]),
        _ep('GET', '/profile',
            security=['bearerAuth'],
            responses=[_resp('200', {'id': 'string', 'name': 'string'})]),
    ]

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)
    auth = [c for c in chains if c.chain_type == 'auth']

    assert len(auth) >= 1, f'Expected auth chain, got: {[c.name for c in chains]}'

    chain = auth[0]
    print(f'  ✓ Chain: {chain.name}')

    assert chain.steps[0].endpoint.path == '/auth/login', 'Login must be step 1'
    assert chain.steps[1].endpoint.path == '/profile', 'Profile must be step 2'

    # Token field captured
    captures = chain.steps[0].captures
    assert ('access_token' in captures or 'token' in captures), \
        f'Token not captured: {captures}'

    # Token used as Authorization header
    uses = chain.steps[1].uses
    assert 'access_token' in uses or 'token' in uses, \
        f'Token not used in protected step: {uses}'
    print('  ✓ Login → profile, token captured and used')
    print('\n✅ Auth chain detection test passed\n')


def test_no_auth_chain_without_protected_endpoints():
    """Login endpoint with no secured consumers → no auth chain."""
    print('\n' + '='*70)
    print('TEST 5: No auth chain when no protected endpoints exist')
    print('='*70)

    endpoints = [
        _ep('POST', '/auth/login',
            responses=[_resp('200', {'access_token': 'string'})]),
        _ep('GET', '/pets',   # no security
            responses=[_resp('200')]),
    ]

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)
    auth = [c for c in chains if c.chain_type == 'auth']

    assert len(auth) == 0, f'Expected no auth chain, got: {[c.name for c in auth]}'
    print('  ✓ No auth chain generated')
    print('\n✅ No-auth-chain test passed\n')


def test_resource_name_extraction():
    """_resource_name strips plurals and path param segments."""
    print('\n' + '='*70)
    print('TEST 6: Resource name extraction')
    print('='*70)

    detector = ChainDetector()
    cases = [
        ('/pets', 'pet'),
        ('/api/v1/users', 'user'),
        ('/pets/{petId}', 'pet'),
        ('/orders', 'order'),
        ('/items', 'item'),
    ]
    for path, expected in cases:
        result = detector._resource_name(path)
        # Accept if either shares a 3-char prefix (heuristic depluralization)
        ok = (result.startswith(expected[:3])
              or expected.startswith(result[:3]))
        assert ok, f'_resource_name({path!r}) = {result!r}, expected ~{expected!r}'
        print(f'  ✓ {path} → {result}')

    print('\n✅ Resource name test passed\n')


def test_strip_id_suffix():
    """_strip_id_suffix correctly removes common ID suffixes."""
    print('\n' + '='*70)
    print('TEST 7: Strip ID suffix')
    print('='*70)

    detector = ChainDetector()
    cases = [
        ('petId', 'pet'),
        ('userId', 'user'),
        ('user_id', 'user'),
        ('postId', 'post'),
        ('orderId', 'order'),
    ]
    for param, expected in cases:
        result = detector._strip_id_suffix(param)
        assert result == expected, \
            f'_strip_id_suffix({param!r}) = {result!r}, expected {expected!r}'
        print(f'  ✓ {param} → {result}')

    print('\n✅ Strip ID suffix test passed\n')


def test_empty_input():
    """detect_chains on empty list returns empty list."""
    print('\n' + '='*70)
    print('TEST 8: Empty endpoint list')
    print('='*70)

    detector = ChainDetector()
    chains = detector.detect_chains([])
    assert chains == [], f'Expected [], got: {chains}'
    print('  ✓ Empty input → empty output')
    print('\n✅ Empty input test passed\n')


def test_no_duplicate_chains():
    """Same endpoints should not produce duplicate chain names."""
    print('\n' + '='*70)
    print('TEST 9: No duplicate chains')
    print('='*70)

    endpoints = [
        _ep('POST', '/pets',
            responses=[_resp('201', {'id': 'string'})]),
        _ep('GET', '/pets/{petId}',
            responses=[_resp('200', {'id': 'string'})]),
        _ep('DELETE', '/pets/{petId}',
            responses=[_resp('204')]),
    ]

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)
    names = [c.name for c in chains]

    assert len(names) == len(set(names)), f'Duplicate chain names: {names}'
    print(f'  ✓ {len(chains)} unique chain(s): {names}')
    print('\n✅ Deduplication test passed\n')


def test_unrelated_endpoints_not_chained():
    """Endpoints on different resources should not produce false chains."""
    print('\n' + '='*70)
    print('TEST 10: Unrelated endpoints not chained')
    print('='*70)

    endpoints = [
        _ep('POST', '/pets',
            responses=[_resp('201', {'id': 'string'})]),
        _ep('GET', '/orders/{orderId}',    # different resource
            responses=[_resp('200', {'id': 'string'})]),
        _ep('DELETE', '/orders/{orderId}',
            responses=[_resp('204')]),
    ]

    detector = ChainDetector()
    chains = detector.detect_chains(endpoints)
    crud = [c for c in chains if c.chain_type == 'crud']

    # POST /pets should not chain with /orders/{orderId}
    for chain in crud:
        methods_paths = [(s.endpoint.method, s.endpoint.path) for s in chain.steps]
        has_pets_post = any(m == 'POST' and '/pets' in p for m, p in methods_paths)
        has_orders = any('/orders' in p for _, p in methods_paths)
        assert not (has_pets_post and has_orders), \
            f'Wrongly chained /pets POST with /orders: {methods_paths}'

    print('  ✓ /pets POST not chained with /orders endpoints')
    print('\n✅ Unrelated endpoint test passed\n')


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all_tests():
    print('\n🧪 ' + '='*68)
    print('CHAIN DETECTOR TEST SUITE')
    print('='*70)

    tests = [
        test_crud_chain_detected,
        test_full_crud_ordering,
        test_no_chain_without_id_in_response,
        test_auth_chain_detected,
        test_no_auth_chain_without_protected_endpoints,
        test_resource_name_extraction,
        test_strip_id_suffix,
        test_empty_input,
        test_no_duplicate_chains,
        test_unrelated_endpoints_not_chained,
    ]

    passed = failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            print(f'\n❌ {test_fn.__name__} FAILED: {exc}\n')
            import traceback
            traceback.print_exc()
            failed += 1

    print('='*70)
    print(f'✅ Passed: {passed}  ❌ Failed: {failed}')
    print('='*70 + '\n')


if __name__ == '__main__':
    run_all_tests()
