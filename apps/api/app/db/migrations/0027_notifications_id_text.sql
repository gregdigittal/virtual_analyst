-- R7-10: Use string id with ntf_ prefix for notifications (consistent with other entities).
alter table notifications alter column id drop default;
alter table notifications alter column id type text using id::text;
