from scripts.import_skill_metadata import candidates_for


def test_skill_importer_selects_only_canonical_skill_paths():
    assert candidates_for(
        "ECC-main.zip",
        "ECC-main/skills/verification-loop/SKILL.md",
    ) == ("ECC", "verification-loop")

    # Agent-specific copies, translations and docs are not duplicated.
    assert candidates_for(
        "ECC-main.zip",
        "ECC-main/.agents/skills/verification-loop/SKILL.md",
    ) is None
    assert candidates_for(
        "ECC-main.zip",
        "ECC-main/docs/es/skills/verification-loop/SKILL.md",
    ) is None

    assert candidates_for(
        "Desktop2222.zip",
        "Desktop2222/Astra-main/.agent/skills/astra-dev/SKILL.md",
    ) == ("Astra", "astra-dev")
    assert candidates_for(
        "Desktop2222.zip",
        "Desktop2222/GLM-V-main/skills/glmv-caption/SKILL.md",
    ) == ("GLM-V", "glmv-caption")
    assert candidates_for(
        "Desktop2222.zip",
        "Desktop2222/rea-main/rea-main/.agents/skills/reverse-engineer-anything/SKILL.md",
    ) == ("REA", "reverse-engineer-anything")


    assert candidates_for(
        "teddy-skill-candidates.zip",
        "TEDDY_SKILLS/ECC/verification-loop/SKILL.md",
    ) == ("ECC", "verification-loop")


def test_skill_importer_rejects_path_traversal():
    assert candidates_for("ECC-main.zip", "../skills/evil/SKILL.md") is None
    assert candidates_for("ECC-main.zip", "ECC-main/skills/../../outside/SKILL.md") is None
