"""Configuration contracts for cross-account logical identities."""

from __future__ import annotations

from pathlib import Path

import pytest

from immich_memories.config_loader import Config


def test_identity_config_loads_accounts_subjects_and_boolean_groups(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("KATIE_IMMICH_API_KEY", "katie-secret")
    path = tmp_path / "config.yaml"
    path.write_text(
        """
immich:
  url: http://immich.test:2283
  api_key: primary-secret
identities:
  accounts:
    michael:
      api_key: primary-secret
    katie:
      api_key: ${KATIE_IMMICH_API_KEY}
  subjects:
    lucas:
      display_name: Lucas
      people:
        michael: michael-lucas-id
        katie: katie-lucas-id
    asher:
      display_name: Asher
      people:
        michael: michael-asher-id
        katie: katie-asher-id
    michael:
      display_name: Michael
      people:
        michael: michael-self-id
        katie: katie-michael-id
    katie:
      display_name: Katie
      people:
        michael: michael-katie-id
        katie: katie-self-id
  groups:
    kids:
      display_name: All Kids
      subjects: [lucas, asher]
      match: any
    parents:
      display_name: Michael & Katie
      subjects: [michael, katie]
      match: all
""".strip()
    )

    config = Config.from_yaml(path)

    assert config.identities.accounts["katie"].api_key == "katie-secret"
    assert config.identities.subjects["lucas"].people == {
        "michael": "michael-lucas-id",
        "katie": "katie-lucas-id",
    }
    assert config.identities.groups["kids"].match == "any"
    assert config.identities.groups["parents"].match == "all"


def test_composite_group_and_floating_event_load(tmp_path: Path) -> None:
    source = tmp_path / "config.yaml"
    source.write_text(
        """
identities:
  accounts:
    family:
      api_key: key
  subjects:
    mom:
      display_name: Mom
      people: {family: mom-id}
    asher:
      display_name: Asher
      people: {family: asher-id}
    lucas:
      display_name: Lucas
      people: {family: lucas-id}
  groups:
    mothers_day:
      display_name: Mom & Kids
      required: [mom]
      any_of: [asher, lucas]
      event_rule:
        month: 5
        weekday: sunday
        occurrence: 2
""".strip()
    )

    group = Config.from_yaml(source).identities.groups["mothers_day"]

    assert group.boolean_label == "REQUIRED + ANY"
    assert group.event_rule is not None
    assert group.event_rule.date_for_year(2026).isoformat() == "2026-05-10"


def test_group_rejects_ambiguous_boolean_syntax(tmp_path: Path) -> None:
    source = tmp_path / "config.yaml"
    source.write_text(
        """
identities:
  accounts:
    family:
      api_key: key
  subjects:
    mom:
      display_name: Mom
      people: {family: mom-id}
  groups:
    invalid:
      display_name: Invalid
      subjects: [mom]
      required: [mom]
""".strip()
    )

    with pytest.raises(ValueError, match="either subjects\\+match or required\\+any_of"):
        Config.from_yaml(source)


def test_identity_account_secret_template_survives_save(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KATIE_IMMICH_API_KEY", "do-not-persist")
    source = tmp_path / "config.yaml"
    source.write_text(
        """
identities:
  accounts:
    katie:
      api_key: ${KATIE_IMMICH_API_KEY}
""".strip()
    )

    saved = tmp_path / "saved.yaml"
    Config.from_yaml(source).save_yaml(saved)

    text = saved.read_text()
    assert "do-not-persist" not in text
    assert "${KATIE_IMMICH_API_KEY}" in text
