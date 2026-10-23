PRAGMA foreign_keys = ON;

CREATE TABLE Author (
    AuthorId INTEGER PRIMARY KEY,
    FullName TEXT NOT NULL CHECK(length(trim(FullName)) > 0)
);
CREATE TABLE Publisher (
    PublisherId INTEGER PRIMARY KEY,
    Name TEXT NOT NULL CHECK(length(trim(Name)) > 0)
);
CREATE TABLE Category (
    CategoryId INTEGER PRIMARY KEY,
    Name TEXT NOT NULL UNIQUE CHECK(length(trim(Name)) > 0)
);
CREATE TABLE Book (
    BookId INTEGER PRIMARY KEY,
    PublisherId INTEGER NOT NULL REFERENCES Publisher(PublisherId),
    Title TEXT NOT NULL CHECK(length(trim(Title)) > 0),
    Isbn TEXT UNIQUE,
    PublicationYear INTEGER NOT NULL CHECK(PublicationYear BETWEEN 1450 AND 2200)
);
CREATE TABLE BookAuthor (
    BookId INTEGER NOT NULL REFERENCES Book(BookId),
    AuthorId INTEGER NOT NULL REFERENCES Author(AuthorId),
    PRIMARY KEY(BookId, AuthorId)
);
CREATE TABLE BookCategory (
    BookId INTEGER NOT NULL REFERENCES Book(BookId),
    CategoryId INTEGER NOT NULL REFERENCES Category(CategoryId),
    PRIMARY KEY(BookId, CategoryId)
);
CREATE TABLE Branch (
    BranchId INTEGER PRIMARY KEY,
    Name TEXT NOT NULL CHECK(length(trim(Name)) > 0),
    Address TEXT NOT NULL
);
CREATE TABLE StorageLocation (
    LocationId INTEGER PRIMARY KEY,
    BranchId INTEGER NOT NULL REFERENCES Branch(BranchId),
    ShelfCode TEXT NOT NULL,
    UNIQUE(BranchId, ShelfCode)
);
CREATE TABLE BookCopy (
    CopyId INTEGER PRIMARY KEY,
    BookId INTEGER NOT NULL REFERENCES Book(BookId),
    LocationId INTEGER NOT NULL REFERENCES StorageLocation(LocationId),
    InventoryNumber TEXT NOT NULL UNIQUE,
    ConditionStatus TEXT NOT NULL DEFAULT 'usable'
        CHECK(ConditionStatus IN ('usable','repair','lost','withdrawn'))
);
CREATE TABLE Reader (
    ReaderId INTEGER PRIMARY KEY,
    CardNumber TEXT NOT NULL UNIQUE,
    FullName TEXT NOT NULL CHECK(length(trim(FullName)) > 0),
    Email TEXT,
    Status TEXT NOT NULL DEFAULT 'active' CHECK(Status IN ('active','blocked'))
);
CREATE TABLE Employee (
    EmployeeId INTEGER PRIMARY KEY,
    FullName TEXT NOT NULL CHECK(length(trim(FullName)) > 0),
    Role TEXT NOT NULL CHECK(Role IN ('librarian','cashier','administrator'))
);
CREATE TABLE Reservation (
    ReservationId INTEGER PRIMARY KEY,
    ReaderId INTEGER NOT NULL REFERENCES Reader(ReaderId),
    BookId INTEGER NOT NULL REFERENCES Book(BookId),
    PickupBranchId INTEGER NOT NULL REFERENCES Branch(BranchId),
    ReservedAt TEXT NOT NULL CHECK(julianday(ReservedAt) IS NOT NULL),
    Status TEXT NOT NULL DEFAULT 'queued' CHECK(Status IN ('queued','fulfilled','cancelled'))
);
CREATE UNIQUE INDEX OneQueuedReservationPerReaderBookBranch
    ON Reservation(ReaderId,BookId,PickupBranchId) WHERE Status='queued';

CREATE TABLE Loan (
    LoanId INTEGER PRIMARY KEY,
    ReaderId INTEGER NOT NULL REFERENCES Reader(ReaderId),
    IssuedByEmployeeId INTEGER NOT NULL REFERENCES Employee(EmployeeId),
    IssuedAt TEXT NOT NULL CHECK(julianday(IssuedAt) IS NOT NULL)
);
CREATE TABLE LoanItem (
    LoanItemId INTEGER PRIMARY KEY,
    LoanId INTEGER NOT NULL REFERENCES Loan(LoanId),
    CopyId INTEGER NOT NULL REFERENCES BookCopy(CopyId),
    DueAt TEXT NOT NULL CHECK(julianday(DueAt) IS NOT NULL),
    ReturnedAt TEXT CHECK(ReturnedAt IS NULL OR julianday(ReturnedAt) IS NOT NULL),
    ReturnedByEmployeeId INTEGER REFERENCES Employee(EmployeeId),
    CHECK((ReturnedAt IS NULL AND ReturnedByEmployeeId IS NULL) OR
          (ReturnedAt IS NOT NULL AND ReturnedByEmployeeId IS NOT NULL))
);
CREATE UNIQUE INDEX OneActiveLoanPerCopy ON LoanItem(CopyId) WHERE ReturnedAt IS NULL;

CREATE TABLE Fine (
    FineId INTEGER PRIMARY KEY,
    LoanItemId INTEGER NOT NULL UNIQUE REFERENCES LoanItem(LoanItemId),
    AmountCents INTEGER NOT NULL CHECK(typeof(AmountCents)='integer' AND AmountCents>0),
    AssessedAt TEXT NOT NULL CHECK(julianday(AssessedAt) IS NOT NULL),
    Reason TEXT NOT NULL
);
CREATE TABLE Payment (
    PaymentId INTEGER PRIMARY KEY,
    FineId INTEGER NOT NULL REFERENCES Fine(FineId),
    ReceivedByEmployeeId INTEGER NOT NULL REFERENCES Employee(EmployeeId),
    AmountCents INTEGER NOT NULL CHECK(typeof(AmountCents)='integer' AND AmountCents>0),
    PaidAt TEXT NOT NULL CHECK(julianday(PaidAt) IS NOT NULL),
    ReceiptNumber TEXT NOT NULL UNIQUE
);

CREATE VIEW ReaderDebt AS
SELECT l.ReaderId, SUM(f.AmountCents - COALESCE(p.PaidCents,0)) AS DebtCents
FROM Fine f JOIN LoanItem li ON li.LoanItemId=f.LoanItemId
JOIN Loan l ON l.LoanId=li.LoanId
LEFT JOIN (SELECT FineId,SUM(AmountCents) AS PaidCents FROM Payment GROUP BY FineId) p
    ON p.FineId=f.FineId
GROUP BY l.ReaderId;

CREATE VIEW AvailableCopy AS
SELECT bc.CopyId,bc.BookId,sl.BranchId,bc.InventoryNumber
FROM BookCopy bc JOIN StorageLocation sl ON sl.LocationId=bc.LocationId
WHERE bc.ConditionStatus='usable'
AND NOT EXISTS(SELECT 1 FROM LoanItem li WHERE li.CopyId=bc.CopyId AND li.ReturnedAt IS NULL);

CREATE TRIGGER ValidateLoanItemDates BEFORE INSERT ON LoanItem BEGIN
    SELECT CASE WHEN julianday(NEW.DueAt) <
        (SELECT julianday(IssuedAt) FROM Loan WHERE LoanId=NEW.LoanId)
        THEN RAISE(ABORT,'Due date precedes issue date') END;
    SELECT CASE WHEN NEW.ReturnedAt IS NOT NULL AND julianday(NEW.ReturnedAt) <
        (SELECT julianday(IssuedAt) FROM Loan WHERE LoanId=NEW.LoanId)
        THEN RAISE(ABORT,'Return date precedes issue date') END;
END;
CREATE TRIGGER ValidateLoanItemUpdate BEFORE UPDATE ON LoanItem BEGIN
    SELECT CASE WHEN NEW.LoanId!=OLD.LoanId OR NEW.CopyId!=OLD.CopyId
        THEN RAISE(ABORT,'Issued copy and loan are immutable') END;
    SELECT CASE WHEN julianday(NEW.DueAt) <
        (SELECT julianday(IssuedAt) FROM Loan WHERE LoanId=NEW.LoanId)
        THEN RAISE(ABORT,'Due date precedes issue date') END;
    SELECT CASE WHEN NEW.ReturnedAt IS NOT NULL AND julianday(NEW.ReturnedAt) <
        (SELECT julianday(IssuedAt) FROM Loan WHERE LoanId=NEW.LoanId)
        THEN RAISE(ABORT,'Return date precedes issue date') END;
    SELECT CASE WHEN OLD.ReturnedAt IS NOT NULL AND
        (NEW.ReturnedAt IS NULL OR NEW.ReturnedAt!=OLD.ReturnedAt)
        THEN RAISE(ABORT,'Completed return is immutable') END;
END;
CREATE TRIGGER CheckNewIssue BEFORE INSERT ON LoanItem WHEN NEW.ReturnedAt IS NULL BEGIN
    SELECT CASE WHEN (SELECT r.Status FROM Reader r JOIN Loan l ON l.ReaderId=r.ReaderId
        WHERE l.LoanId=NEW.LoanId)!='active' THEN RAISE(ABORT,'Reader is blocked') END;
    SELECT CASE WHEN (SELECT ConditionStatus FROM BookCopy WHERE CopyId=NEW.CopyId)!='usable'
        THEN RAISE(ABORT,'Copy is not usable') END;
    SELECT CASE WHEN COALESCE((SELECT d.DebtCents FROM ReaderDebt d JOIN Loan l ON l.ReaderId=d.ReaderId
        WHERE l.LoanId=NEW.LoanId),0)>0 THEN RAISE(ABORT,'Reader has unpaid fines') END;
    SELECT CASE WHEN (SELECT COUNT(*) FROM LoanItem li JOIN Loan l ON l.LoanId=li.LoanId
        WHERE li.ReturnedAt IS NULL AND l.ReaderId=(SELECT ReaderId FROM Loan WHERE LoanId=NEW.LoanId))>=5
        THEN RAISE(ABORT,'Reader reached five copy limit') END;
END;
CREATE TRIGGER FineRequiresLateReturn BEFORE INSERT ON Fine BEGIN
    SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM LoanItem li WHERE li.LoanItemId=NEW.LoanItemId
        AND li.ReturnedAt IS NOT NULL AND date(li.ReturnedAt)>date(li.DueAt))
        THEN RAISE(ABORT,'Fine requires a late completed return') END;
    SELECT CASE WHEN julianday(NEW.AssessedAt)<
        (SELECT julianday(ReturnedAt) FROM LoanItem WHERE LoanItemId=NEW.LoanItemId)
        THEN RAISE(ABORT,'Fine date precedes return') END;
END;
CREATE TRIGGER PaymentCannotOverpay BEFORE INSERT ON Payment BEGIN
    SELECT CASE WHEN NEW.AmountCents>(SELECT AmountCents FROM Fine WHERE FineId=NEW.FineId)
        -COALESCE((SELECT SUM(AmountCents) FROM Payment WHERE FineId=NEW.FineId),0)
        THEN RAISE(ABORT,'Payment exceeds fine balance') END;
    SELECT CASE WHEN julianday(NEW.PaidAt)<(SELECT julianday(AssessedAt) FROM Fine WHERE FineId=NEW.FineId)
        THEN RAISE(ABORT,'Payment date precedes fine') END;
END;
CREATE TRIGGER PaymentUpdateCannotOverpay BEFORE UPDATE ON Payment BEGIN
    SELECT CASE WHEN NEW.AmountCents>(SELECT AmountCents FROM Fine WHERE FineId=NEW.FineId)
        -COALESCE((SELECT SUM(AmountCents) FROM Payment WHERE FineId=NEW.FineId AND PaymentId!=OLD.PaymentId),0)
        THEN RAISE(ABORT,'Payment exceeds fine balance') END;
    SELECT CASE WHEN julianday(NEW.PaidAt)<(SELECT julianday(AssessedAt) FROM Fine WHERE FineId=NEW.FineId)
        THEN RAISE(ABORT,'Payment date precedes fine') END;
END;
CREATE TRIGGER FineCannotBecomeLessThanPayments BEFORE UPDATE OF AmountCents ON Fine BEGIN
    SELECT CASE WHEN NEW.AmountCents<COALESCE((SELECT SUM(AmountCents) FROM Payment WHERE FineId=OLD.FineId),0)
        THEN RAISE(ABORT,'Fine is smaller than received payments') END;
END;
