# Модель библиотечного обслуживания

## Сущности и атрибуты

| Сущность | Назначение | Атрибуты |
| --- | --- | --- |
| Author | Автор | `AuthorId` INTEGER (PK; обязательный); `FullName` TEXT (обязательный) |
| Publisher | Издательство | `PublisherId` INTEGER (PK; обязательный); `Name` TEXT (обязательный) |
| Category | Категория | `CategoryId` INTEGER (PK; обязательный); `Name` TEXT (обязательный) |
| Book | Издание | `BookId` INTEGER (PK; обязательный); `PublisherId` INTEGER (FK; обязательный); `Title` TEXT (обязательный); `Isbn` TEXT (UQ; NULL допустим); `PublicationYear` INTEGER (обязательный) |
| BookAuthor | Авторство | `BookId` INTEGER (PK FK; обязательный); `AuthorId` INTEGER (PK FK; обязательный) |
| BookCategory | Рубрикация | `BookId` INTEGER (PK FK; обязательный); `CategoryId` INTEGER (PK FK; обязательный) |
| Branch | Филиал | `BranchId` INTEGER (PK; обязательный); `Name` TEXT (обязательный); `Address` TEXT (обязательный) |
| StorageLocation | Место хранения | `LocationId` INTEGER (PK; обязательный); `BranchId` INTEGER (FK; обязательный); `ShelfCode` TEXT (обязательный) |
| BookCopy | Экземпляр | `CopyId` INTEGER (PK; обязательный); `BookId` INTEGER (FK; обязательный); `LocationId` INTEGER (FK; обязательный); `InventoryNumber` TEXT (UQ; обязательный); `ConditionStatus` TEXT (обязательный) |
| Reader | Читатель | `ReaderId` INTEGER (PK; обязательный); `CardNumber` TEXT (UQ; обязательный); `FullName` TEXT (обязательный); `Email` TEXT (NULL допустим); `Status` TEXT (обязательный) |
| Employee | Сотрудник | `EmployeeId` INTEGER (PK; обязательный); `FullName` TEXT (обязательный); `Role` TEXT (обязательный) |
| Reservation | Бронирование | `ReservationId` INTEGER (PK; обязательный); `ReaderId` INTEGER (FK; обязательный); `BookId` INTEGER (FK; обязательный); `PickupBranchId` INTEGER (FK; обязательный); `ReservedAt` TEXT (обязательный); `Status` TEXT (обязательный) |
| Loan | Выдача | `LoanId` INTEGER (PK; обязательный); `ReaderId` INTEGER (FK; обязательный); `IssuedByEmployeeId` INTEGER (FK; обязательный); `IssuedAt` TEXT (обязательный) |
| LoanItem | Позиция выдачи | `LoanItemId` INTEGER (PK; обязательный); `LoanId` INTEGER (FK; обязательный); `CopyId` INTEGER (FK; обязательный); `DueAt` TEXT (обязательный); `ReturnedAt` TEXT (NULL допустим); `ReturnedByEmployeeId` INTEGER (FK; NULL допустим) |
| Fine | Штраф | `FineId` INTEGER (PK; обязательный); `LoanItemId` INTEGER (FK UQ; обязательный); `AmountCents` INTEGER (обязательный); `AssessedAt` TEXT (обязательный); `Reason` TEXT (обязательный) |
| Payment | Платёж | `PaymentId` INTEGER (PK; обязательный); `FineId` INTEGER (FK; обязательный); `ReceivedByEmployeeId` INTEGER (FK; обязательный); `AmountCents` INTEGER (обязательный); `PaidAt` TEXT (обязательный); `ReceiptNumber` TEXT (UQ; обязательный) |

## Кардинальности

| Родитель → дочерняя сущность | Кратность | Внешний ключ |
| --- | --- | --- |
| Publisher → Book | 1 — 0..* | `PublisherId` |
| Book → BookAuthor | 1 — 0..* | `BookId` |
| Author → BookAuthor | 1 — 0..* | `AuthorId` |
| Book → BookCategory | 1 — 0..* | `BookId` |
| Category → BookCategory | 1 — 0..* | `CategoryId` |
| Book → BookCopy | 1 — 0..* | `BookId` |
| Branch → StorageLocation | 1 — 0..* | `BranchId` |
| StorageLocation → BookCopy | 1 — 0..* | `LocationId` |
| Reader → Reservation | 1 — 0..* | `ReaderId` |
| Book → Reservation | 1 — 0..* | `BookId` |
| Branch → Reservation | 1 — 0..* | `PickupBranchId` |
| Reader → Loan | 1 — 0..* | `ReaderId` |
| Employee → Loan | 1 — 0..* | `IssuedByEmployeeId` |
| Loan → LoanItem | 1 — 1..* | `LoanId` |
| BookCopy → LoanItem | 1 — 0..* | `CopyId` |
| Employee → LoanItem | 0..1 — 0..* | `ReturnedByEmployeeId` |
| LoanItem → Fine | 1 — 0..1 | `LoanItemId` |
| Fine → Payment | 1 — 0..* | `FineId` |
| Employee → Payment | 1 — 0..* | `ReceivedByEmployeeId` |

Две связи многие ко многим представлены отдельными сущностями: BookAuthor и BookCategory. Пара внешних ключей в каждой образует составной первичный ключ.

Кратность Loan–LoanItem 1..* относится к завершённой операции выдачи. В сценарии документ и как минимум одна позиция записываются одной транзакцией; один внешний ключ не обеспечивает обязательного наличия дочернего объекта.

ReturnedByEmployeeId допускает NULL до возврата. ReturnedAt и принявший сотрудник заполняются одновременно. Сотрудник, который выдал книгу, и сотрудник, который принял её обратно, имеют разные роли.

BookCopy–LoanItem отражает всю историю экземпляра. Частичный уникальный индекс отдельно запрещает две активные позиции для одного экземпляра. LoanItem–Fine допускает максимум один штраф; Fine–Payment допускает частичные платежи, суммарная величина которых не превышает начисление.

Отрицательные и нулевые платежи запрещены. Деньги хранятся целым числом копеек. Доступность экземпляров и остатки задолженности вычисляются представлениями AvailableCopy и ReaderDebt.

Учебная схема проверяет возможность выдачи: активный читатель, пригодный экземпляр, отсутствие задолженности и не более пяти активных книг. Вся проверка и запись выполняется на SQLite с включёнными внешними ключами.
