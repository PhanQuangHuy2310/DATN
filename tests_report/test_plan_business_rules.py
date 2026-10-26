import unittest
from api_core.domain.plan_constraints import plan_business_errors

class PlanConstraintTests(unittest.TestCase):
    def test_advance_bands_exact_boundaries(self):
        for code,amount,should_error in (
            ("ADVANCE_SMALL",9_999_999,False), ("ADVANCE_SMALL",10_000_000,True),
            ("ADVANCE_MEDIUM",9_999_999,True),("ADVANCE_MEDIUM",10_000_000,False),
            ("ADVANCE_MEDIUM",50_000_000,False),("ADVANCE_MEDIUM",50_000_001,True),
            ("ADVANCE_LARGE",50_000_000,True),("ADVANCE_LARGE",50_000_001,False)):
            with self.subTest(code=code,amount=amount):
                self.assertEqual(bool(plan_business_errors(code,{"amount":amount})),should_error)

    def test_long_leave_requires_three_days(self):
        self.assertIn("end_date",plan_business_errors("LEAVE_LONG",{"start_date":"2026-11-03","end_date":"2026-11-04"}))
        self.assertEqual(plan_business_errors("LEAVE_LONG",{"start_date":"2026-11-03","end_date":"2026-11-05"}),{})
        self.assertIn("end_date",plan_business_errors("LEAVE_ANNUAL",{"start_date":"2026-11-05","end_date":"2026-11-03"}))

    def test_vehicle_booking_requires_valid_datetime(self):
        good={"start_time":"2026-11-03T09:00:00+07:00","end_time":"2026-11-03T11:00:00+07:00"}
        self.assertFalse(plan_business_errors("ROOM_VEHICLE",good))
        self.assertIn("end_time",plan_business_errors("ROOM_VEHICLE",{**good,"end_time":"2026-11-03T08:00:00+07:00"}))
        self.assertIn("start_time",plan_business_errors("ROOM_VEHICLE",{**good,"start_time":"2026-11-03T09:00:00"}))

    def test_p0_unchanged(self):
        self.assertEqual(plan_business_errors("LEAVE",{}),{})
        self.assertEqual(plan_business_errors("EQUIPMENT",{"amount":60000000}),{})

if __name__ == '__main__':
    unittest.main()
