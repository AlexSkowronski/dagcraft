# SharePoint Excel report

Read a budget workbook with a sheet per quarter from SharePoint, compare it
with actual spend from Azure SQL, and publish a workbook with a sheet per
table back to SharePoint.

Needs `pip install "dagcraft-pipelines[azure,excel]"`, and an identity with
Microsoft Graph access to the site's files (see
[SharePoint](../connections/sharepoint.md#signing-in)).

```yaml
# configs/budget_report.yaml
pipeline:
  name: budget_report
  env_file: .env

params:
  year: 2026

connections:
  finance:
    type: sharepoint
    site: contoso.sharepoint.com/sites/Finance
    folder: Reports/${params.year}
  warehouse:
    type: azure_sql
    server: ${env:SQL_SERVER}
    database: ${env:SQL_DATABASE}

steps:
  # Four sheets, Q1 to Q4, read as one table with a "quarter" column.
  - id: budget
    type: read
    connection: finance
    path: Budget ${params.year}.xlsx
    args:
      sheet_name: [Q1, Q2, Q3, Q4]
      sheet_column: quarter

  - id: actuals
    type: read
    connection: warehouse
    query_file: sql/actuals_by_department.sql
    params:
      year: ${params.year}

  - id: comparison
    type: transform
    inputs:
      data: budget
      actuals: actuals
    operations:
      - join: {right: actuals, on: [department, quarter], how: left}
      - fill_nulls: {actual: 0}
      - derive:
          variance: actual - budget

  # One sheet per input, named after it.
  - id: publish
    type: write
    connection: finance
    path: Budget vs actuals ${params.year}.xlsx
    inputs:
      Comparison: comparison
      Budget: budget
```

```sql
-- sql/actuals_by_department.sql: spend per department and quarter in :year
SELECT
    department,
    CONCAT('Q', DATEPART(QUARTER, posted_on)) AS quarter,
    SUM(amount) AS actual
FROM finance.ledger
WHERE YEAR(posted_on) = :year
GROUP BY department, DATEPART(QUARTER, posted_on)
```

```bash
dagcraft configs/budget_report.yaml --dry-run
dagcraft configs/budget_report.yaml
```
