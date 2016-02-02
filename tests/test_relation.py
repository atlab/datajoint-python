from inspect import getmembers
import re

import itertools
from numpy.testing import assert_array_equal
import numpy as np
from nose.tools import assert_raises, assert_equal, assert_not_equal, \
    assert_false, assert_true, assert_list_equal, \
    assert_tuple_equal, assert_dict_equal, raises
from . import schema
from pymysql import IntegrityError, ProgrammingError
import datajoint as dj
from datajoint import utils
from unittest.mock import patch


def relation_selector(attr):
    try:
        return issubclass(attr, dj.BaseRelation)
    except TypeError:
        return False


class TestRelation:
    """
    Test base relations: insert, delete
    """

    def __init__(self):
        self.user = schema.User()
        self.subject = schema.Subject()
        self.experiment = schema.Experiment()
        self.trial = schema.Trial()
        self.ephys = schema.Ephys()
        self.channel = schema.Ephys.Channel()
        self.img = schema.Image()
        self.trash = schema.UberTrash()

    def test_contents(self):
        """
        test the ability of tables to self-populate using the contents property
        """

        # test contents
        assert_true(self.user)
        assert_true(len(self.user) == len(self.user.contents))
        u = self.user.fetch(order_by=['username'])
        assert_list_equal(list(u['username']), sorted([s[0] for s in self.user.contents]))

        # test prepare
        assert_true(self.subject)
        assert_true(len(self.subject) == len(self.subject.contents))
        u = self.subject.fetch(order_by=['subject_id'])
        assert_list_equal(list(u['subject_id']), sorted([s[0] for s in self.subject.contents]))

    @raises(KeyError)
    def test_misnamed_attribute(self):
        self.user.insert1(dict(user="Bob"))

    @raises(dj.DataJointError)
    def test_empty_insert(self):
        self.user.insert1(())

    @raises(dj.DataJointError)
    def test_wrong_arguments_insert(self):
        self.user.insert1(('First', 'Second'))

    @raises(dj.DataJointError)
    def test_wrong_insert_type(self):
        self.user.insert1(3)

    def test_replace(self):
        """
        Test replacing or ignoring duplicate entries
        """
        key = dict(subject_id=7)
        date = "2015-01-01"
        self.subject.insert1(
            dict(key, real_id=7, date_of_birth=date, subject_notes=""))
        assert_equal(date, str((self.subject & key).fetch1['date_of_birth']), 'incorrect insert')
        date = "2015-01-02"
        self.subject.insert1(
            dict(key, real_id=7, date_of_birth=date, subject_notes=""), skip_duplicates=True)
        assert_not_equal(date, str((self.subject & key).fetch1['date_of_birth']),
                         'inappropriate replace')
        self.subject.insert1(
            dict(key, real_id=7, date_of_birth=date, subject_notes=""), replace=True)
        assert_equal(date, str((self.subject & key).fetch1['date_of_birth']), "replace failed")

    def test_delete_quick(self):
        """Tests quick deletion"""
        tmp = np.array([
            (2, 'Klara', 'monkey', '2010-01-01', ''),
            (1, 'Peter', 'mouse', '2015-01-01', '')],
            dtype=self.subject.heading.as_dtype)
        self.subject.insert(tmp)
        s = self.subject & ('subject_id in (%s)' % ','.join(str(r) for r in tmp['subject_id']))
        assert_true(len(s) == 2, 'insert did not work.')
        s.delete_quick()
        assert_true(len(s) == 0, 'delete did not work.')

    def test_skip_duplicate(self):
        """Tests if duplicates are properly skipped."""
        tmp = np.array([
            (2, 'Klara', 'monkey', '2010-01-01', ''),
            (2, 'Klara', 'monkey', '2010-01-01', ''),
            (1, 'Peter', 'mouse', '2015-01-01', '')],
            dtype=self.subject.heading.as_dtype)
        self.subject.insert(tmp, skip_duplicates=True)

    @raises(IntegrityError)
    def test_not_skip_duplicate(self):
        """Tests if duplicates are not skipped."""
        tmp = np.array([
            (2, 'Klara', 'monkey', '2010-01-01', ''),
            (2, 'Klara', 'monkey', '2010-01-01', ''),
            (1, 'Peter', 'mouse', '2015-01-01', '')],
            dtype=self.subject.heading.as_dtype)
        self.subject.insert(tmp, skip_duplicates=False)

    def test_blob_insert(self):
        """Tests inserting and retrieving blobs."""
        X = np.random.randn(20, 10)
        self.img.insert1((1, X))
        Y = self.img.fetch()[0]['img']
        assert_true(np.all(X == Y), 'Inserted and retrieved image are not identical')

    @raises(ProgrammingError)
    def test_drop(self):
        """Tests dropping tables"""
        dj.config['safemode'] = True
        with patch.object(utils, "input", create=True, return_value='yes'):
            self.trash.drop()
        dj.config['safemode'] = False
        self.trash.fetch()

    def test_table_regexp(self):
        """Test whether table names are matched by regular expressions"""
        tiers = [dj.Imported, dj.Manual, dj.Lookup, dj.Computed]
        for name, rel in getmembers(schema, relation_selector):
            assert_true(re.match(rel._regexp, rel().table_name),
                        'Regular expression does not match for {name}'.format(name=name))

            for tier in itertools.filterfalse(lambda t: issubclass(rel, t), tiers):
                assert_false(re.match(tier._regexp, rel().table_name),
                      'Regular expression matches for {name} but should not'.format(name=name))
