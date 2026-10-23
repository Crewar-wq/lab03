from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from demo_scenarios import connect

class DatabaseChecks(unittest.TestCase):
    def setUp(self):self.db=connect()
    def tearDown(self):self.db.close()

    def issue(self,copy=1,reader=1,loan=1,item=1,due='2026-10-15T18:00:00'):
        self.db.execute("INSERT INTO Loan VALUES(?,?,1,'2026-10-01T10:00:00')",(loan,reader))
        self.db.execute('INSERT INTO LoanItem VALUES(?,?,?, ?,NULL,NULL)',(item,loan,copy,due))

    def late_return(self):
        self.issue()
        self.db.execute("UPDATE LoanItem SET ReturnedAt='2026-10-18T11:00:00',ReturnedByEmployeeId=1 WHERE LoanItemId=1")
        self.db.execute("INSERT INTO Fine VALUES(1,1,3000,'2026-10-18T11:05:00','Просрочка')")

    def pay(self,amount=1000,identity=1,paid='2026-10-18T11:10:00'):
        self.db.execute('INSERT INTO Payment VALUES(?,1,2,?,?,?)',(identity,amount,paid,f'RCPT-{identity}'))

    def rejected(self,sql,args=()):
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute(sql,args)

    def test_foreign_keys_enabled_and_consistent(self):
        self.assertEqual(self.db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_nonexistent_parent_is_rejected(self):
        self.rejected("INSERT INTO BookCopy VALUES(9,999,1,'INV-009','usable')")

    def test_unique_inventory_number(self):
        self.rejected("INSERT INTO BookCopy VALUES(9,1,1,'INV-001','usable')")

    def test_unique_reader_card(self):
        self.rejected("INSERT INTO Reader VALUES(9,'CARD-001','Читатель X',NULL,'active')")

    def test_many_to_many_author_and_category(self):
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM BookAuthor WHERE BookId=1').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM BookCategory WHERE BookId=1').fetchone()[0],2)
        self.rejected('INSERT INTO BookAuthor VALUES(1,1)')
        self.rejected('INSERT INTO BookCategory VALUES(1,1)')

    def test_shelf_unique_within_branch(self):
        self.rejected("INSERT INTO StorageLocation VALUES(9,1,'ИТ-01')")
        self.db.execute("INSERT INTO StorageLocation VALUES(9,2,'ИТ-01')")

    def test_reservation_queue_uniqueness_and_history(self):
        self.db.execute("INSERT INTO Reservation VALUES(1,1,1,1,'2026-10-01T09:00:00','queued')")
        self.rejected("INSERT INTO Reservation VALUES(2,1,1,1,'2026-10-01T09:01:00','queued')")
        self.db.execute("UPDATE Reservation SET Status='cancelled' WHERE ReservationId=1")
        self.db.execute("INSERT INTO Reservation VALUES(2,1,1,1,'2026-10-01T09:02:00','queued')")

    def test_copy_cannot_have_two_active_loans(self):
        self.issue()
        self.rejected("INSERT INTO LoanItem VALUES(2,1,1,'2026-10-15T18:00:00',NULL,NULL)")

    def test_copy_becomes_available_after_return(self):
        self.issue()
        self.assertIsNone(self.db.execute('SELECT 1 FROM AvailableCopy WHERE CopyId=1').fetchone())
        self.db.execute("UPDATE LoanItem SET ReturnedAt='2026-10-14T11:00:00',ReturnedByEmployeeId=1 WHERE LoanItemId=1")
        self.assertIsNotNone(self.db.execute('SELECT 1 FROM AvailableCopy WHERE CopyId=1').fetchone())
        self.issue(loan=2,item=2)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM LoanItem WHERE CopyId=1').fetchone()[0],2)

    def test_blocked_reader_cannot_receive_copy(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError,'blocked'):self.issue(reader=2)

    def test_repair_copy_cannot_be_issued(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError,'usable'):self.issue(copy=4)

    def test_reader_cannot_exceed_five_active_copies(self):
        for identity in range(5,10):
            self.db.execute("INSERT INTO BookCopy VALUES(?,1,1,?,'usable')",(identity,f'INV-{identity:03}'))
        self.db.execute("INSERT INTO Loan VALUES(1,1,1,'2026-10-01T10:00:00')")
        for identity,copy in enumerate([1,2,3,5,6],1):
            self.db.execute("INSERT INTO LoanItem VALUES(?,1,?,'2026-10-15T18:00:00',NULL,NULL)",(identity,copy))
        self.rejected("INSERT INTO LoanItem VALUES(6,1,7,'2026-10-15T18:00:00',NULL,NULL)")

    def test_due_date_must_not_precede_issue(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError,'Due date'):self.issue(due='2026-09-30T10:00:00')

    def test_return_date_and_employee_are_paired(self):
        self.issue()
        self.rejected("UPDATE LoanItem SET ReturnedAt='2026-10-14T11:00:00' WHERE LoanItemId=1")
        self.rejected('UPDATE LoanItem SET ReturnedByEmployeeId=1 WHERE LoanItemId=1')

    def test_return_cannot_precede_issue(self):
        self.issue()
        self.rejected("UPDATE LoanItem SET ReturnedAt='2026-09-30T11:00:00',ReturnedByEmployeeId=1 WHERE LoanItemId=1")

    def test_completed_return_cannot_be_reopened(self):
        self.late_return()
        self.rejected('UPDATE LoanItem SET ReturnedAt=NULL,ReturnedByEmployeeId=NULL WHERE LoanItemId=1')

    def test_fine_requires_completed_late_return(self):
        self.issue()
        self.rejected("INSERT INTO Fine VALUES(1,1,1000,'2026-10-18T11:05:00','Просрочка')")
        self.db.execute("UPDATE LoanItem SET ReturnedAt='2026-10-14T11:00:00',ReturnedByEmployeeId=1 WHERE LoanItemId=1")
        self.rejected("INSERT INTO Fine VALUES(1,1,1000,'2026-10-18T11:05:00','Просрочка')")

    def test_fine_is_unique_for_each_loan_item(self):
        self.late_return()
        self.rejected("INSERT INTO Fine VALUES(2,1,3000,'2026-10-18T11:05:00','Просрочка')")

    def test_money_must_be_positive_integer_cents(self):
        self.late_return()
        for value in [0,-100,1.5]:
            self.rejected("INSERT INTO Payment VALUES(9,1,2,?,'2026-10-18T11:10:00','RCPT-X')",(value,))

    def test_partial_and_full_payment_balance(self):
        self.late_return();self.pay()
        self.assertEqual(self.db.execute('SELECT DebtCents FROM ReaderDebt WHERE ReaderId=1').fetchone()[0],2000)
        self.pay(2000,2)
        self.assertEqual(self.db.execute('SELECT DebtCents FROM ReaderDebt WHERE ReaderId=1').fetchone()[0],0)

    def test_payment_cannot_exceed_balance(self):
        self.late_return();self.pay()
        self.rejected("INSERT INTO Payment VALUES(2,1,2,2001,'2026-10-18T11:15:00','RCPT-2')")

    def test_payment_update_cannot_overpay(self):
        self.late_return();self.pay();self.pay(1000,2)
        self.rejected('UPDATE Payment SET AmountCents=2001 WHERE PaymentId=1')

    def test_fine_cannot_be_reduced_below_payments(self):
        self.late_return();self.pay()
        self.rejected('UPDATE Fine SET AmountCents=999 WHERE FineId=1')

    def test_payment_must_not_precede_fine(self):
        self.late_return()
        with self.assertRaisesRegex(sqlite3.IntegrityError,'date'):self.pay(paid='2026-10-17T11:00:00')

    def test_unpaid_fine_blocks_next_issue(self):
        self.late_return()
        with self.assertRaisesRegex(sqlite3.IntegrityError,'unpaid'):self.issue(copy=2,loan=2,item=2)
        self.pay(3000)
        self.issue(copy=2,loan=3,item=3)

    def test_three_scenarios_run_end_to_end(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/demo_scenarios.py')],check=True,capture_output=True,text=True)
        data=json.loads(result.stdout)
        self.assertEqual(len(data['scenarios']),3)
        self.assertEqual(data['scenarios'][2]['final_debt_cents'],0)
        self.assertEqual(data['foreign_key_check'],[])
        self.assertEqual(data['integrity_check'],'ok')

if __name__=='__main__':unittest.main()
