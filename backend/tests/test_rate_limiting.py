def test_rate_limiting(client):
    # Health endpoint is limited to 5/minute
    # Since other tests might have hit /health, we clear limits if possible or we just do 5 hits and expect the last one or two to fail.
    # A better approach: We just hit it 6 times. At least one of them MUST be 429.
    status_codes = []
    for _ in range(6):
        response = client.get("/health")
        status_codes.append(response.status_code)
        
    assert 429 in status_codes
        
    assert "error" in response.json()
