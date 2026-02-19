# tests/test_models.py
from where_the_plow.models import (
    PointGeometry,
    FeatureProperties,
    Feature,
    Pagination,
    FeatureCollection,
    StatsResponse,
)


def test_point_geometry():
    g = PointGeometry(coordinates=[-52.73, 47.56])
    assert g.type == "Point"
    assert g.coordinates == [-52.73, 47.56]


def test_feature():
    f = Feature(
        geometry=PointGeometry(coordinates=[-52.73, 47.56]),
        properties=FeatureProperties(
            vehicle_id="v1",
            description="Test Plow",
            vehicle_type="LOADER",
            speed=13.4,
            bearing=135,
            is_driving="maybe",
            timestamp="2026-02-19T12:00:00Z",
        ),
    )
    assert f.type == "Feature"
    assert f.geometry.coordinates[0] == -52.73


def test_feature_collection_with_pagination():
    fc = FeatureCollection(
        features=[],
        pagination=Pagination(limit=200, count=0, has_more=False),
    )
    assert fc.type == "FeatureCollection"
    assert fc.pagination.has_more is False
    assert fc.pagination.next_cursor is None


def test_stats_response():
    s = StatsResponse(
        total_positions=100,
        total_vehicles=10,
        active_vehicles=5,
    )
    assert s.total_positions == 100


def test_coverage_feature_collection():
    from where_the_plow.models import (
        CoverageFeature,
        CoverageFeatureCollection,
        CoverageProperties,
        LineStringGeometry,
    )

    fc = CoverageFeatureCollection(
        features=[
            CoverageFeature(
                geometry=LineStringGeometry(
                    coordinates=[[-52.73, 47.56], [-52.74, 47.57]]
                ),
                properties=CoverageProperties(
                    vehicle_id="v1",
                    vehicle_type="TA PLOW TRUCK",
                    description="2307 TA PLOW TRUCK",
                    timestamps=["2026-02-19T10:00:05Z", "2026-02-19T10:00:35Z"],
                ),
            )
        ]
    )
    assert fc.type == "FeatureCollection"
    assert len(fc.features) == 1
    assert fc.features[0].geometry.type == "LineString"
    assert len(fc.features[0].properties.timestamps) == 2
