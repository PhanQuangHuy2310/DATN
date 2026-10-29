from unittest import TestCase
from api_core.catalog.availability import request_option_blocker


class RequestMenuAvailabilityTests(TestCase):
    def test_missing_code(self):
        self.assertEqual('TYPE_NOT_REGISTERED',request_option_blocker(None,'A')[0])
    def test_disabled(self):
        self.assertEqual('TYPE_INACTIVE',request_option_blocker(('A',False,False,False),'A')[0])
    def test_lifecycle_mismatch(self):
        self.assertEqual('LIFECYCLE_MISMATCH',request_option_blocker(('B',True,True,True),'A')[0])
    def test_missing_publication(self):
        self.assertEqual('NO_PUBLISHED_RELEASE',request_option_blocker(('A',True,False,True),'A')[0])
    def test_missing_requester_grant(self):
        self.assertEqual('REQUESTER_SCOPE_DENIED',request_option_blocker(('A',True,True,False),'A')[0])
    def test_can_create(self):
        self.assertEqual((None,None),request_option_blocker(('A',True,True,True),'A'))
