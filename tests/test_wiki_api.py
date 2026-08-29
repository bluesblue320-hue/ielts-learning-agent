from fastapi.testclient import TestClient

from app.main import create_app
from app.wiki.errors import WikiUnavailableError
from app.wiki.identity import normalize_wiki_identity
from app.wiki.service import WikiService, get_wiki_service


def _client() -> TestClient:
    return TestClient(create_app())


def test_wiki_index_is_read_only_and_returns_all_pages() -> None:
    application = create_app()
    paths = application.openapi()["paths"]
    assert set(paths["/knowledge/writing/wiki"]) == {"get"}
    assert set(paths["/knowledge/writing/wiki/{page_id}"]) == {"get"}
    response = TestClient(application).get("/knowledge/writing/wiki")
    assert response.status_code == 200
    body = response.json()
    assert body["wiki_version"] == "ielts-writing-wiki-v1"
    assert body["navigation_version"] == "writing-wiki-navigation-v1"
    assert len(body["pages"]) == 58


def test_wiki_detail_exposes_grounded_content_and_structural_authority() -> None:
    response = _client().get(
        "/knowledge/writing/wiki/writing-task2-task-response-band-7"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["wiki_version"] == "ielts-writing-wiki-v1"
    assert body["navigation_version"] == "writing-wiki-navigation-v1"
    assert body["page"]["page_id"] == "writing-task2-task-response-band-7"
    assert body["knowledge"][0]["knowledge_id"] == "writing-task-response-band-7"
    assert len(body["relations"]) == 3
    assert {relation["authority"] for relation in body["relations"]} == {
        "application_structural"
    }


def test_wiki_query_resolves_exact_id_and_normalized_title() -> None:
    client = _client()
    by_id = client.get("/knowledge/writing/wiki", params={"q": "writing-task2"})
    by_title = client.get(
        "/knowledge/writing/wiki", params={"q": "  ＷＲＩＴＩＮＧ   ＴＡＳＫ ２ "}
    )
    assert by_id.status_code == by_title.status_code == 200
    assert by_id.json()["page"]["page_id"] == "writing-task2"
    assert by_title.json()["page"]["page_id"] == "writing-task2"


def test_wiki_api_returns_frozen_safe_lookup_errors() -> None:
    client = _client()
    unknown_page = client.get("/knowledge/writing/wiki/writing-task2-unknown")
    unknown_lookup = client.get(
        "/knowledge/writing/wiki", params={"q": "No Such Page"}
    )
    empty_lookup = client.get("/knowledge/writing/wiki", params={"q": "   "})
    invalid_lookup = client.get("/knowledge/writing/wiki", params={"q": "x" * 121})
    invalid_page = client.get("/knowledge/writing/wiki/Invalid Page")
    assert unknown_page.status_code == 404
    assert unknown_page.json()["error"]["code"] == "wiki_page_not_found"
    assert unknown_lookup.status_code == 404
    assert unknown_lookup.json()["error"]["code"] == "wiki_page_not_found"
    assert empty_lookup.status_code == 400
    assert empty_lookup.json()["error"]["code"] == "wiki_lookup_invalid"
    assert invalid_lookup.status_code == 422
    assert invalid_lookup.json()["error"]["code"] == "request_invalid"
    assert invalid_page.status_code == 422
    assert invalid_page.json()["error"]["code"] == "request_invalid"


def test_invalid_internal_wiki_state_maps_to_safe_503() -> None:
    application = create_app()

    def unavailable() -> None:
        raise WikiUnavailableError("private internal details")

    application.dependency_overrides[get_wiki_service] = unavailable
    response = TestClient(application).get("/knowledge/writing/wiki")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "wiki_unavailable",
            "message": "Wiki is temporarily unavailable.",
            "fields": [],
        }
    }


def test_ambiguous_wiki_lookup_maps_to_safe_400() -> None:
    application = create_app()
    service = WikiService()
    identity = normalize_wiki_identity("Writing Task 2")
    service._title_index[identity] = (
        service.get_page("writing-task2"),
        service.get_page("writing-task2-assessment"),
    )
    application.dependency_overrides[get_wiki_service] = lambda: service
    response = TestClient(application).get(
        "/knowledge/writing/wiki", params={"q": "Writing Task 2"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "wiki_lookup_ambiguous"


def test_wiki_mutation_routes_do_not_exist() -> None:
    client = _client()
    for method in ("post", "put", "patch", "delete"):
        response = client.request(
            method.upper(), "/knowledge/writing/wiki", json={}
        )
        assert response.status_code == 405
