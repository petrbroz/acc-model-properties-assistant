# Model Properties Query Language Guide

The **Model Properties Query Language (MPQL)** is a JSON-based query syntax for filtering and retrieving design element properties from a **Model Properties index**. The index is generated for design files hosted in **Autodesk Construction Cloud** using the **ACC Model Properties API** (part of **Autodesk Platform Services**). This guide explains how to construct valid MPQL queries.

## Query Structure

A valid MPQL query consists of:

- A `query` object defining custom filter conditions; only elements matching these filters will be returned
- An optional `columns` object specifying which properties to retrieve

### Example Query

```json
{
  "query": {
    "$eq": ["s.props.p5678efgh", "'Walls'"]
  },
  "columns": {
    "s.svf2Id": true,
    "Name": "s.props.p1234abcd",
    "Width": "s.props.p2233ffee"
  }
}
```

## Property Paths

Properties must always be specified using **property paths** such as `s.props.<key>` where the key is a hexadecimal value prefixed with `p`, for example, `p5678efgh`. The list of all available properties and their keys can be retrieved from the Model Properties index.

There are also several **metadata properties** such as:

- `s.svf2Id` - unique ID of the design element
- `s.views` - number of views in which the element is visible

## Conditions

MPQL supports various operators to filter elements based on their properties:

| Operator   | Description                           | Example  |
|------------|---------------------------------------|----------|
| `$eq`      | Exact match                           | `{ "$eq": ["s.props.p1234abcd", "'Concrete'"] }` |
| `$ne`      | Not equal                             | `{ "$ne": ["s.props.p1234abcd", "'Steel'"] }` |
| `$gt`      | Greater than                          | `{ "$gt": ["s.props.p2233ffee", 100] }` |
| `$ge`      | Greater than or equal                 | `{ "$ge": ["s.props.p2233ffee", 50] }` |
| `$lt`      | Less than                             | `{ "$lt": ["s.props.p2233ffee", 500] }` |
| `$le`      | Less than or equal                    | `{ "$le": ["s.props.p2233ffee", 200] }` |
| `$in`      | Match any value in a list             | `{ "$in": { "s.props.p3344ccdd": ["'Steel'", "'Concrete'"] }}` |
| `$not`     | Negate a condition                    | `{ "$not": { "$eq": ["s.props.p1234abcd", "'Wood'"] } }` |
| `$and`     | Combine multiple conditions (AND)     | `{ "$and": [{ "$eq": ["s.props.p5678efgh", "'Doors'"] }, { "$gt": ["s.props.p2233ffee", 200] }] }` |
| `$or`      | Combine multiple conditions (OR)      | `{ "$or": [{ "$eq": ["s.props.p1234abcd", "'Steel'"] }, { "$eq": ["s.props.p1234abcd", "'Concrete'"] }] }` |
| `$like`    | Pattern matching (wildcards `%`)      | `{ "$like": ["s.props.p5678efgh", "'%Wall%'"] }` |
| `$between` | Match value within a range            | `{ "$between": { "s.props.p2233ffee": [100, 200] } }` |
| `$isnull`  | Match a value that is null            | `{ "$isnull": "s.props.p1234abcd" }` |
| `$notnull` | Match a value that is not null        | `{ "$notnull": "s.props.p1234abcd" }` |

## Expressions

MPQL supports the following expressions in both filter queries and column selections:

| Expression | Description                               | Example |
|------------|-------------------------------------------|---------|
| `$neg`     | Negates the value of an expression        | `{ "$neg": "s.props.p1234abcd" }` |
| `$add`     | Adds two or more expressions              | `{ "$add": ["s.props.p1234abcd", 100] }` |
| `$sub`     | Subtracts two or more expressions         | `{ "$sub": [100, "s.props.p1234abcd"] }` |
| `$mul`     | Multiplies two or more expressions        | `{ "$mul": ["s.props.p1234abcd", 2] }` |
| `$div`     | Divides two or more expressions           | `{ "$div": ["s.props.p1234abcd", 2] }` |
| `$mod`     | Module-divides two or more expressions    | `{ "$mod": ["s.props.p1234abcd", 10] }` |
| `$nullif`  | Returns 2nd expression if 1st one is null | `{ "$nullif": ["s.props.p1234abcd", 0] }` |
| `$count`   | Returns count of values in expression     | `{ "$count": "s.props.p1234abcd" }` |
| `$max`     | Returns maximum of values in expression   | `{ "$max": "s.props.p1234abcd" }` |
| `$min`     | Returns minimum of values in expression   | `{ "$min": "s.props.p1234abcd" }` |

## Column Selection

The `columns` object specifies which properties to retrieve.

### Column Selection Syntax

- **Key-value pairs** where:  
  - The **key** is an alias (or property key).  
  - The **value** is `"s.props.<property_key>"` or `true` (for all properties).

### Examples

#### ✅ Return only specific properties

```json
{
  "query": { "$eq": ["s.props.p5678efgh", "Walls"] },
  "columns": {
    "s.svf2Id": true,
    "Name": "s.props.p1234abcd",
    "Height": "s.props.p2233ffee"
  }
}
```

#### ✅ Return all properties (omit `columns` field)

```json
{
  "query": { "$eq": ["s.props.p5678efgh", "Walls"] }
}
```

#### ✅ Return property values without renaming

```json
{
  "query": { "$eq": ["s.props.p5678efgh", "Doors"] },
  "columns": {
    "s.props.p1234abcd": true,
    "s.props.p3344ccdd": true
  }
}
```

#### ✅ Return number of elements matching a filter

```json
{
  "query": { "$eq": ["s.props.p5678efgh", "Doors"] },
  "columns": {
    "Count": { "$count": "s.props.p5678efgh" }
  }
}
```

#### ✅ Return the smallest and largest value of a property

```json
{
  "query": { "$eq": ["s.props.p5678efgh", "Walls"] },
  "columns": {
    "Minimum": { "$min": "s.props.p1234abcd" },
    "Maximum": { "$max": "s.props.p1234abcd" }
  }
}
```

## Example Queries

### Find all walls and return only their names

```json
{
  "query": {
    "$like": ["s.props.p5678efgh", "'%Wall%'"]
  },
  "columns": {
    "Name": "s.props.p1234abcd"
  }
}
```  

### Find doors taller than 200 and return name, height, and material

```json
{
  "query": {
    "$and": [
      { "$eq": ["s.props.p5678efgh", "Doors"] },
      { "$gt": ["s.props.p2233ffee", 200] }
    ]
  },
  "columns": {
    "Name": "s.props.p1234abcd",
    "Height": "s.props.p2233ffee",
    "Material": "s.props.p9988aabb"
  }
}
```  

### Find elements made of concrete or steel

```json
{
  "query": {
    "$in": ["s.props.p4455ccdd", ["Concrete", "Steel"]]
  }
}
```

### Find visible beams heavier than 100kg

```json
{
  "query": {
    "$and": [
      { "$eq": ["s.props.p5678efgh", "Beams"] },
      { "$eq": ["s.props.p1122aabb", true] },
      { "$gt": ["s.props.p3344ccdd", 100] }
    ]
  },
  "columns": {
    "Name": "s.props.p1234abcd",
    "Weight": "s.props.p3344ccdd"
  }
}
```

## Limitations

- When calculating aggregates such as the maximum value of a property, **metadata properties** such as `s.svf2Id` cannot be used in `columns`.
- When using pattern matching, always wrap the string containing wildcards with single-quotes, for example, `{ "$like": ["s.props.p5678efgh", "'%Wall%'"] }`.

## Resources

- https://aps.autodesk.com/en/docs/acc/v1/tutorials/model-properties/query-ref/