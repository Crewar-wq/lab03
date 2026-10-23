-- Fictional teaching data. All timestamps belong to the same demonstration timeline.
INSERT INTO Author VALUES (1,'Автор А'),(2,'Автор Б');
INSERT INTO Publisher VALUES (1,'Учебное издательство');
INSERT INTO Category VALUES (1,'Информационные технологии'),(2,'Программирование');
INSERT INTO Book VALUES (1,1,'Основы программирования','9780000000001',2025),
                       (2,1,'Базы данных','9780000000002',2024);
INSERT INTO BookAuthor VALUES (1,1),(1,2),(2,2);
INSERT INTO BookCategory VALUES (1,1),(1,2),(2,1);
INSERT INTO Branch VALUES (1,'Главный филиал','Учебный адрес 1'),(2,'Филиал 2','Учебный адрес 2');
INSERT INTO StorageLocation VALUES (1,1,'ИТ-01'),(2,2,'ИТ-02');
INSERT INTO BookCopy VALUES (1,1,1,'INV-001','usable'),(2,1,1,'INV-002','usable'),
    (3,2,2,'INV-003','usable'),(4,2,1,'INV-004','repair');
INSERT INTO Reader VALUES (1,'CARD-001','Читатель А','reader-a@example.invalid','active'),
    (2,'CARD-002','Читатель Б',NULL,'blocked');
INSERT INTO Employee VALUES (1,'Библиотекарь А','librarian'),(2,'Кассир А','cashier');
