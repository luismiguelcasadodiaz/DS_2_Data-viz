# Real counts
I checked the real count with bash, to have a reference at this moment of the project that helps me to validate if previous steps were correct.

```sh
cat data* > customers
cut -d, -f2 customers | sort | uniq -c
4619639 cart
      4 event_type
1045014 purchase
3167270 remove_from_cart
7704235 view
```

This count matches the percentages shown in the subject.

# Seed up charts

We have 16,536,158 so each statisitcs is a time consuming operation.

I discovered the PostgreSQL `materialized` view, that is a view that once executed keeps the results in such a way that the next call to this view no statistics are calculated.

It is posible to refresh materialized views whan original date change.