===========
reportsmith
===========

A small, dependency-free Python library for building reports programmatically
and exporting them to **Markdown** or a **standalone styled HTML** document.

.. code-block:: python

   from reportsmith import Report, bold

   report = Report("Q3 Sales Report", author="Jane Doe")
   with report.section("Overview") as s:
       s.paragraph(["Revenue was ", bold("up 12%"), " quarter over quarter."])

   report.save_markdown("report.md")
   report.save_html("report.html")

.. toctree::
   :maxdepth: 2

   user-guide
   api-reference
