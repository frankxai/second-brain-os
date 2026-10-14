import os
from pathlib import Path
import pytest
from sbo_ingestion import audit
from sbo_ingestion.continuity import check_sis_installed

def test_missing_explicit_sis_root_cannot_fall_back_to_installed_ambient_root(tmp_path, monkeypatch):
    ambient=tmp_path/'installed';ambient.mkdir()
    monkeypatch.setenv('SBO_SIS_ROOT',str(ambient))
    assert check_sis_installed(tmp_path/'selected-but-missing') is False

def test_a_file_is_not_an_installed_sis_directory(tmp_path):
    selected=tmp_path/'not-a-directory';selected.write_text('fixture')
    assert check_sis_installed(selected) is False

def test_atomic_write_accepts_valid_destination_near_platform_path_limit(tmp_path):
    # The destination fits the platform limit. Temporary bookkeeping must not
    # make that otherwise valid destination unwritable on Windows or POSIX.
    name_length=240-len(str(tmp_path))-1 if os.name=='nt' else 235
    assert name_length>5
    target=tmp_path/('r'*(name_length-5)+'.json')
    audit.atomic_write_text(target,'{"state":"complete"}\n')
    assert target.read_text()=='{"state":"complete"}\n'
    assert set(tmp_path.iterdir())=={target}

def test_atomic_replacement_failure_preserves_previous_data_and_cleans_temporary(tmp_path,monkeypatch):
    target=tmp_path/'receipt.json';target.write_text('before')
    def refuse(*_):raise PermissionError('simulated locked destination')
    monkeypatch.setattr(audit.os,'replace',refuse)
    with pytest.raises(PermissionError):audit.atomic_write_text(target,'after')
    assert target.read_text()=='before'
    assert set(tmp_path.iterdir())=={target}
