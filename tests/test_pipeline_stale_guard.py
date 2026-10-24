from unittest.mock import patch

import pytest

import main as pipeline


def test_pipeline_accepts_unchanged_recent_reading_without_claiming_new_ingest():
    city = {'id': 9, 'api_name': 'Monterrey', 'is_active': True, 'latitude': 25.7, 'longitude': -100.3}
    update_result = {
        'readingInserted': False,
        'unchangedReading': True,
        'cityStatusUpdated': True,
        'insertError': None,
        'lookupError': None,
        'updateError': None,
        'validationErrors': None,
    }

    with (
        patch.object(pipeline, 'get_required_env', return_value={'WAQI_API_TOKEN': 'test'}),
        patch.object(pipeline, 'get_cities_for_provider', return_value=({'provider': 'waqi'}, [city])),
        patch.object(pipeline, 'check_if_update_needed', return_value={'needsUpdate': True}),
        patch.object(pipeline, 'fetch_provider_air_quality', return_value={'status': 'success'}),
        patch.object(pipeline, 'enrich_with_weather_context', return_value={'status': 'success'}),
        patch.object(pipeline, 'update_city', return_value=update_result),
        patch.object(pipeline, 'compute_inter_city_delay', return_value=0),
        patch.object(pipeline, 'delay'),
    ):
        summary = pipeline.main()

    assert summary['readings_inserted'] == 0
    assert summary['skipped_unchanged'] == 1
    assert summary['failed_updates'] == 0


def test_pipeline_rejects_stale_only_batch_even_if_all_fetches_were_http_200():
    city = {'id': 9, 'api_name': 'Monterrey', 'is_active': True}
    update_result = {
        'readingInserted': False,
        'unchangedReading': False,
        'validationErrors': ['stale_reading_timestamp'],
        'insertError': None,
        'updateError': None,
    }

    with (
        patch.object(pipeline, 'get_required_env', return_value={'WAQI_API_TOKEN': 'test'}),
        patch.object(pipeline, 'get_cities_for_provider', return_value=({'provider': 'waqi'}, [city])),
        patch.object(pipeline, 'check_if_update_needed', return_value={'needsUpdate': True}),
        patch.object(pipeline, 'fetch_provider_air_quality', return_value={'status': 'success'}),
        patch.object(pipeline, 'enrich_with_weather_context', return_value={'status': 'success'}),
        patch.object(pipeline, 'update_city', return_value=update_result),
        patch.object(pipeline, 'compute_inter_city_delay', return_value=0),
        patch.object(pipeline, 'delay'),
        patch.object(pipeline, 'log_pipeline_summary') as log_summary,
    ):
        with pytest.raises(pipeline.PipelineRunError):
            pipeline.main()

    summary = log_summary.call_args.args[0]
    assert summary['readings_inserted'] == 0
    assert summary['failed_updates'] == 1
    assert summary['validation_failures'] == 1
