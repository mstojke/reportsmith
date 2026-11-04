===========
reportsmith
===========

A small, dependency-free Python library for building reports programmatically
and exporting them to **Markdown**, a **standalone styled HTML** document,
**LaTeX**, or **PDF**.

See the `examples site <https://mstojke.github.io/reportsmith/>`_ for every example report rendered in all
four formats, next to the script that made it.

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
