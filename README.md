# IndieCourier

A Micropub endpoint implemented in FastAPI.

#### Note
In order to parse the date from a provided URL (for updating posts), the site must have a `dt-published` property somewhere in the post's HTML. For example, a Jekyll layout could include something like this:

```html
{% assign date_format = "%B %d, %Y at %-I:%M %p %Z" %}
<time datetime="{{ page.date | date_to_xmlschema }}">{{ page.date | date: date_format }}</time></a>
```

The output would be something like this:

```html
<time class="dt-published" datetime="2025-10-09T00:00:00-05:00">October 9, 2025</time>
```

[IndieCourier](https://github.com/saundersresearch/IndieCourier) © 2026 [Adam Saunders](https://adamsaunders.net) (GNU AGPLv3 License). [Modest CSS](https://github.com/markdowncss/modest) by John Otander (MIT License).