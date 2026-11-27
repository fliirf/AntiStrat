import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from synth import make_dataset  # noqa: E402


@pytest.fixture(scope="session")
def synth_data(tmp_path_factory):
    return make_dataset(tmp_path_factory.mktemp("grid"))


@pytest.fixture(scope="session")
def pipeline_out(synth_data, tmp_path_factory):
    from antistrat import pipeline

    out = tmp_path_factory.mktemp("out")
    centers = out / "site_centers.json"
    pipeline.extract(synth_data, out, workers=1)
    pipeline.sites(out, centers)
    pipeline.features(out, centers)
    return out, centers


@pytest.fixture(scope="session")
def trained(pipeline_out, synth_data, tmp_path_factory):
    from antistrat import pipeline

    out, _ = pipeline_out
    metrics_path = out / "model_metrics.json"
    agg = tmp_path_factory.mktemp("agg")
    metrics = pipeline.train(out, metrics_path)
    index = pipeline.report(out, synth_data, metrics_path, agg)
    return metrics, index, agg
