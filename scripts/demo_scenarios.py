#!/usr/bin/env python3
"""Execute the three report scenarios in a real, temporary SQLite database."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import sqlite3

ROOT=Path(__file__).resolve().parents[1]

def connect():
    db=sqlite3.connect(':memory:')
    db.row_factory=sqlite3.Row
    db.executescript((ROOT/'schema/library.sql').read_text(encoding='utf-8'))
    db.executescript((ROOT/'schema/demo.sql').read_text(encoding='utf-8'))
    return db

def late_fee(due,returned,rate_cents=1000):
    days=max(0,(datetime.fromisoformat(returned).date()-datetime.fromisoformat(due).date()).days)
    return days*rate_cents

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    db=connect();results=[]
    with db:
        db.execute("INSERT INTO Reader VALUES(3,'CARD-003','Читатель В',NULL,'active')")
        db.execute("INSERT INTO Reservation VALUES(1,3,1,1,'2026-10-01T09:00:00','queued')")
    results.append({'scenario':'Регистрация и бронирование','reader':'CARD-003','book_id':1,'branch_id':1,'reservation_status':'queued'})
    with db:
        copy=db.execute('SELECT CopyId FROM AvailableCopy WHERE BookId=1 AND BranchId=1 ORDER BY CopyId LIMIT 1').fetchone()[0]
        db.execute("INSERT INTO Loan VALUES(1,3,1,'2026-10-01T10:00:00')")
        db.execute("INSERT INTO LoanItem VALUES(1,1,?,'2026-10-15T18:00:00',NULL,NULL)",(copy,))
        db.execute("UPDATE Reservation SET Status='fulfilled' WHERE ReservationId=1")
    assert not db.execute('SELECT 1 FROM AvailableCopy WHERE CopyId=?',(copy,)).fetchone()
    results.append({'scenario':'Выдача книги','loan_id':1,'copy_id':copy,'due_at':'2026-10-15T18:00:00','reservation_status':'fulfilled','copy_available':False})
    due='2026-10-15T18:00:00';returned='2026-10-18T11:00:00'
    amount=late_fee(due,returned)
    with db:
        db.execute('UPDATE LoanItem SET ReturnedAt=?,ReturnedByEmployeeId=1 WHERE LoanItemId=1',(returned,))
        db.execute("INSERT INTO Fine VALUES(1,1,?,'2026-10-18T11:05:00','Просрочка на 3 календарных дня')",(amount,))
        db.execute("INSERT INTO Payment VALUES(1,1,2,1000,'2026-10-18T11:10:00','RCPT-001')")
    debt_after_partial=db.execute('SELECT DebtCents FROM ReaderDebt WHERE ReaderId=3').fetchone()[0]
    with db:
        db.execute("INSERT INTO Payment VALUES(2,1,2,2000,'2026-10-18T11:15:00','RCPT-002')")
    debt=db.execute('SELECT DebtCents FROM ReaderDebt WHERE ReaderId=3').fetchone()[0]
    assert amount==3000 and debt_after_partial==2000 and debt==0
    assert db.execute('SELECT 1 FROM AvailableCopy WHERE CopyId=?',(copy,)).fetchone()
    results.append({'scenario':'Возврат и оплата штрафа','late_calendar_days':3,'rate_cents_per_day':1000,'fine_cents':amount,'payments_cents':[1000,2000],'debt_after_first_payment_cents':debt_after_partial,'final_debt_cents':debt,'copy_available':True})
    data={'sqlite_version':sqlite3.sqlite_version,'scenarios':results,'foreign_key_check':db.execute('PRAGMA foreign_key_check').fetchall(),'integrity_check':db.execute('PRAGMA integrity_check').fetchone()[0]}
    out=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(out,encoding='utf-8',newline='\n')
    print(out,end='')

if __name__=='__main__':main()
