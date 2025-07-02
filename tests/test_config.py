from tests import update_config, get_config


def test_update_config_basic():
    """Test basic config update functionality"""

    original_config = get_config()
    new_settings = {"collection_name": "test_collection"}

    update_config(new_settings)
    updated_config = get_config()

    assert updated_config()["collection_name"] == "test_collection"
    # Reset config to original state
    update_config(original_config())


def test_update_config_multiple_values():
    """Test updating multiple config values"""
    original_config = get_config()
    new_settings = {
        "collection_name": "test_collection",
        "vector_size": 512,
        "distance_metric": "euclidean"
    }

    update_config(new_settings)
    updated_config = get_config()

    assert updated_config()["collection_name"] == "test_collection"
    assert updated_config()["vector_size"] == 512
    assert updated_config()["distance_metric"] == "euclidean"
    # Reset config to original state
    update_config(original_config())


def test_update_config_empty_dict():
    """Test updating with empty dictionary"""
    original_config = get_config()
    update_config({})

    assert get_config() == original_config


def test_update_config_new_key():
    """Test adding new key to config"""
    original_config = get_config()
    new_settings = {"new_key": "new_value"}

    update_config(new_settings)
    updated_config = get_config()

    assert "new_key" in updated_config()
    assert updated_config()["new_key"] == "new_value"
    # Reset config to original state
    update_config(original_config())
