from monday_rotocon import mutations


def test_m_create_item_has_required_vars():
    assert "$board_id: ID!" in mutations.M_CREATE_ITEM
    assert "$item_name: String!" in mutations.M_CREATE_ITEM
    assert "$column_values: JSON" in mutations.M_CREATE_ITEM
    assert "create_item(" in mutations.M_CREATE_ITEM


def test_m_change_values_uses_multi_mutation():
    assert "$item_id: ID!" in mutations.M_CHANGE_VALUES
    assert "$board_id: ID!" in mutations.M_CHANGE_VALUES
    assert "$column_values: JSON!" in mutations.M_CHANGE_VALUES
    assert "change_multiple_column_values" in mutations.M_CHANGE_VALUES


def test_mutations_return_full_item_shape():
    for q in (mutations.M_CREATE_ITEM, mutations.M_CHANGE_VALUES):
        assert "column_values { id type value text }" in q
        assert "updated_at" in q
        assert "name" in q
