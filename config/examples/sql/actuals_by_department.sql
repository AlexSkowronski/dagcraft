-- Actual spend per department and quarter for the year :year (SQL Server).
SELECT
    department,
    CONCAT('Q', DATEPART(QUARTER, posted_on)) AS quarter,
    SUM(amount) AS actual
FROM finance.ledger
WHERE YEAR(posted_on) = :year
GROUP BY department, DATEPART(QUARTER, posted_on)
