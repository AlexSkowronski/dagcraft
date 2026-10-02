-- Orders and revenue per region since :since, for orders with status :status.
SELECT
    c.region,
    COUNT(*) AS orders,
    SUM(o.quantity * o.unit_price) AS revenue
FROM orders AS o
JOIN customers AS c ON c.customer_id = o.customer_id
WHERE o.order_date >= :since
  AND o.status = :status
GROUP BY c.region
ORDER BY revenue DESC
