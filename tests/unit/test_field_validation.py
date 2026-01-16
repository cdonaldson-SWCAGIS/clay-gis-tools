"""
Unit tests for the field validation module.
Tests validation of values against Esri field types.
"""
import unittest
from frontend.components.field_validation import (
    validate_value_for_field_type,
    get_field_type_from_fields,
    _validate_integer,
    _validate_numeric,
    _validate_date,
    NUMERIC_INTEGER_TYPES,
    NUMERIC_FLOAT_TYPES,
    DATE_TYPES,
    STRING_TYPES
)


class TestValidateInteger(unittest.TestCase):
    """Test integer validation."""
    
    def test_valid_positive_integer(self):
        """Test valid positive integer."""
        is_valid, error = _validate_integer("123", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_negative_integer(self):
        """Test valid negative integer."""
        is_valid, error = _validate_integer("-456", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_zero(self):
        """Test zero is valid."""
        is_valid, error = _validate_integer("0", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_invalid_float(self):
        """Test float is invalid for integer field."""
        is_valid, error = _validate_integer("123.45", "=")
        self.assertFalse(is_valid)
        self.assertIn("not a valid integer", error)
    
    def test_invalid_alpha(self):
        """Test alpha characters are invalid."""
        is_valid, error = _validate_integer("abc", "=")
        self.assertFalse(is_valid)
        self.assertIn("not a valid integer", error)
    
    def test_invalid_mixed(self):
        """Test mixed alphanumeric is invalid."""
        is_valid, error = _validate_integer("123abc", "=")
        self.assertFalse(is_valid)
        self.assertIn("not a valid integer", error)
    
    def test_valid_in_operator_multiple_values(self):
        """Test multiple comma-separated integers with IN operator."""
        is_valid, error = _validate_integer("1, 2, 3", "IN")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_invalid_in_operator_with_alpha(self):
        """Test IN operator fails if any value is invalid."""
        is_valid, error = _validate_integer("1, abc, 3", "IN")
        self.assertFalse(is_valid)
        self.assertIn("abc", error)


class TestValidateNumeric(unittest.TestCase):
    """Test numeric (float/double) validation."""
    
    def test_valid_integer(self):
        """Test integer is valid for numeric field."""
        is_valid, error = _validate_numeric("123", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_float(self):
        """Test valid float."""
        is_valid, error = _validate_numeric("123.45", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_negative_float(self):
        """Test valid negative float."""
        is_valid, error = _validate_numeric("-123.45", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_decimal_only(self):
        """Test decimal starting with dot."""
        is_valid, error = _validate_numeric("0.45", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_invalid_alpha(self):
        """Test alpha characters are invalid."""
        is_valid, error = _validate_numeric("abc", "=")
        self.assertFalse(is_valid)
        self.assertIn("not a valid number", error)
    
    def test_invalid_mixed(self):
        """Test mixed alphanumeric is invalid."""
        is_valid, error = _validate_numeric("12.3abc", "=")
        self.assertFalse(is_valid)
        self.assertIn("not a valid number", error)
    
    def test_valid_in_operator_multiple_floats(self):
        """Test multiple comma-separated floats with IN operator."""
        is_valid, error = _validate_numeric("1.5, 2.5, 3.5", "IN")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")


class TestValidateDate(unittest.TestCase):
    """Test date validation."""
    
    def test_valid_date_format(self):
        """Test valid YYYY-MM-DD format."""
        is_valid, error = _validate_date("2024-01-15", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_timestamp(self):
        """Test valid Unix timestamp."""
        is_valid, error = _validate_date("1705320000000", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_arcade_date(self):
        """Test Arcade date() function."""
        is_valid, error = _validate_date("date(2024, 1, 15)", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_valid_timestamp_keyword(self):
        """Test timestamp keyword."""
        is_valid, error = _validate_date("timestamp '2024-01-15'", "=")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_invalid_date_format(self):
        """Test invalid date format."""
        is_valid, error = _validate_date("01/15/2024", "=")
        self.assertFalse(is_valid)
        self.assertIn("not a valid date", error)
    
    def test_invalid_alpha(self):
        """Test alpha string is invalid."""
        is_valid, error = _validate_date("January", "=")
        self.assertFalse(is_valid)
        self.assertIn("not a valid date", error)


class TestValidateValueForFieldType(unittest.TestCase):
    """Test the main validation function with different field types."""
    
    def test_integer_field_valid(self):
        """Test valid value for integer field."""
        is_valid, error = validate_value_for_field_type("123", "esriFieldTypeInteger")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_integer_field_invalid(self):
        """Test invalid value for integer field."""
        is_valid, error = validate_value_for_field_type("abc", "esriFieldTypeInteger")
        self.assertFalse(is_valid)
        self.assertIn("not a valid integer", error)
    
    def test_double_field_valid(self):
        """Test valid value for double field."""
        is_valid, error = validate_value_for_field_type("123.45", "esriFieldTypeDouble")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_double_field_invalid(self):
        """Test invalid value for double field."""
        is_valid, error = validate_value_for_field_type("abc", "esriFieldTypeDouble")
        self.assertFalse(is_valid)
        self.assertIn("not a valid number", error)
    
    def test_date_field_valid(self):
        """Test valid value for date field."""
        is_valid, error = validate_value_for_field_type("2024-01-15", "esriFieldTypeDate")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_date_field_invalid(self):
        """Test invalid value for date field."""
        is_valid, error = validate_value_for_field_type("not-a-date", "esriFieldTypeDate")
        self.assertFalse(is_valid)
        self.assertIn("not a valid date", error)
    
    def test_string_field_always_valid(self):
        """Test string field accepts any value."""
        is_valid, error = validate_value_for_field_type("anything", "esriFieldTypeString")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_string_field_accepts_numbers(self):
        """Test string field accepts numeric strings."""
        is_valid, error = validate_value_for_field_type("123", "esriFieldTypeString")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_null_operator_skips_validation(self):
        """Test IS NULL operator doesn't validate value."""
        is_valid, error = validate_value_for_field_type("", "esriFieldTypeInteger", "IS NULL")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_is_not_null_operator_skips_validation(self):
        """Test IS NOT NULL operator doesn't validate value."""
        is_valid, error = validate_value_for_field_type("", "esriFieldTypeInteger", "IS NOT NULL")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_empty_value_fails(self):
        """Test empty value fails for non-NULL operators."""
        is_valid, error = validate_value_for_field_type("", "esriFieldTypeInteger")
        self.assertFalse(is_valid)
        self.assertIn("required", error)
    
    def test_oid_field_valid(self):
        """Test valid value for OID field."""
        is_valid, error = validate_value_for_field_type("12345", "esriFieldTypeOID")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_small_integer_field_valid(self):
        """Test valid value for small integer field."""
        is_valid, error = validate_value_for_field_type("255", "esriFieldTypeSmallInteger")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_single_field_valid(self):
        """Test valid value for single (float) field."""
        is_valid, error = validate_value_for_field_type("3.14", "esriFieldTypeSingle")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_guid_field_accepts_any(self):
        """Test GUID field accepts any string."""
        is_valid, error = validate_value_for_field_type("{abc-123-def}", "esriFieldTypeGUID")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")
    
    def test_unknown_type_defaults_to_string(self):
        """Test unknown field type is treated as string (no validation)."""
        is_valid, error = validate_value_for_field_type("anything", "esriFieldTypeUnknown")
        self.assertTrue(is_valid)
        self.assertEqual(error, "")


class TestGetFieldTypeFromFields(unittest.TestCase):
    """Test field type lookup from fields_with_types list."""
    
    def test_find_existing_field(self):
        """Test finding a field that exists."""
        fields = [
            {"name": "field1", "type": "esriFieldTypeString"},
            {"name": "field2", "type": "esriFieldTypeInteger"},
            {"name": "field3", "type": "esriFieldTypeDouble"}
        ]
        result = get_field_type_from_fields("field2", fields)
        self.assertEqual(result, "esriFieldTypeInteger")
    
    def test_field_not_found_returns_string(self):
        """Test missing field defaults to string type."""
        fields = [
            {"name": "field1", "type": "esriFieldTypeInteger"}
        ]
        result = get_field_type_from_fields("nonexistent", fields)
        self.assertEqual(result, "esriFieldTypeString")
    
    def test_empty_fields_list(self):
        """Test empty fields list returns string type."""
        result = get_field_type_from_fields("any_field", [])
        self.assertEqual(result, "esriFieldTypeString")
    
    def test_field_without_type_returns_string(self):
        """Test field without type property returns string."""
        fields = [
            {"name": "field1"}  # No type property
        ]
        result = get_field_type_from_fields("field1", fields)
        self.assertEqual(result, "esriFieldTypeString")


class TestFieldTypeConstants(unittest.TestCase):
    """Test that field type constants are defined correctly."""
    
    def test_numeric_integer_types(self):
        """Test numeric integer types list."""
        self.assertIn("esriFieldTypeInteger", NUMERIC_INTEGER_TYPES)
        self.assertIn("esriFieldTypeSmallInteger", NUMERIC_INTEGER_TYPES)
        self.assertIn("esriFieldTypeOID", NUMERIC_INTEGER_TYPES)
    
    def test_numeric_float_types(self):
        """Test numeric float types list."""
        self.assertIn("esriFieldTypeDouble", NUMERIC_FLOAT_TYPES)
        self.assertIn("esriFieldTypeSingle", NUMERIC_FLOAT_TYPES)
    
    def test_date_types(self):
        """Test date types list."""
        self.assertIn("esriFieldTypeDate", DATE_TYPES)
    
    def test_string_types(self):
        """Test string types list."""
        self.assertIn("esriFieldTypeString", STRING_TYPES)
        self.assertIn("esriFieldTypeGUID", STRING_TYPES)
        self.assertIn("esriFieldTypeGlobalID", STRING_TYPES)


if __name__ == "__main__":
    unittest.main()
