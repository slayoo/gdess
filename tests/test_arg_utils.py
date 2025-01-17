import pytest
import os

from co2_diag.formatters.args import options_to_args, is_some_none, nullable_int, nullable_str, valid_year_string, \
    valid_existing_path, valid_writable_path


def test_options_to_args():
    options = {'option1': 'val1', 'option2': 2, 'option3': None, 'option4': True}
    expected = ['--option1', 'val1',
                '--option2', '2',
                '--option3', 'None',
                '--option4', 'True']

    assert options_to_args(options) == expected


def test_a_valid_year():
    assert isinstance(valid_year_string('2021'), str)


def test_an_invalid_year():
    with pytest.raises(Exception):
        valid_year_string('20211234')


def test_a_none_year():
    assert valid_year_string(None) is None


def test_a_nonestr_year():
    assert valid_year_string('none') is None


def test_none_is_some_none():
    assert is_some_none(None) is True


def test_nonestr_is_some_none():
    assert is_some_none('None') is True


def test_not_a_none_string_is_not_none():
    assert is_some_none('no') is False


def test_not_a_none_string_bad_type():
    assert is_some_none([]) is False


def test_nullable_string_to_none_object():
    assert nullable_str('none') is None


def test_nullable_string_bad_type():
    with pytest.raises(Exception):
        nullable_str(5)


def test_nullable_integer_is_none():
    assert nullable_int('none') is None


def test_nullable_integer():
    assert nullable_int(5) == 5


def test_nullable_integer_bad_string():
    with pytest.raises(Exception):
        nullable_int('no')


def test_nullable_integer_bad_type():
    with pytest.raises(Exception):
        nullable_int([])


def test_nonexistent_path_does_not_exist(rootdir):
    with pytest.raises(Exception):
        valid_existing_path(os.path.join(rootdir, 'nonexistent'))


def test_valid_path_is_writable(rootdir):
    p = os.path.join(rootdir, 'footest')
    assert valid_writable_path(p) == p
