#
# epydoc.css: default help page
# Edward Loper
#
# Created [01/30/01 05:18 PM]
# $Id$
#

"""
Predefined help file for the HTML outputter (L{epydoc.html}).

@type HTML_HELP: C{string}
@var HTML_HELP: The contents of the HTML body for the default
   help page.
"""

HTML_HELP = """
<center><h2> API Documentation </h2></center>

<p> This document contains the API (Application Programming Interface)
documentation for this project.  Documentation for the Python objects
defined by the project is divided into separate pages for each
package, module, and class.  The API documentation also includes two
pages containing information about the project as a whole: a trees
page, and an index page.  </p>

<h2> Object Documentation </h2>

  <p>Each <b>Package Documentation</b> page contains: 
  <ul>
    <li> A description of the package. </li>
    <li> A list of the modules and sub-packages contained by the
    package.  </li>
    <li> A summary of the classes defined by the package. </li>
    <li> A summary of the functions defined by the package. </li>
    <li> A summary of the variables defined by the package. </li>
    <li> A detailed description of each funciton defined by the
    package. </li>
    <li> A detailed description of each variable defined by the
    package. </li>
  </ul></p>
  
  <p>Each <b>Module Documentation</b> page contains:
  <ul>
    <li> A description of the module. </li>
    <li> A summary of the classes defined by the module. </li>
    <li> A summary of the functions defined by the module. </li>
    <li> A summary of the variables defined by the module. </li>
    <li> A detailed description of each funciton defined by the
    module. </li>
    <li> A detailed description of each variable defined by the
    module. </li>
  </ul></p>
  
  <p>Each <b>Class Documentation</b> page contains:
  <ul>
    <li> A class inheritence diagram. </li>
    <li> A list of known subclasses. </li>
    <li> A description of the class. </li>
    <li> A summary of the methods defined by the class. </li>
    <li> A summary of the instance variables defined by the class. </li>
    <li> A summary of the class (static) variables defined by the
    class. </li> 
    <li> A detailed description of each method defined by the
    class. </li>
    <li> A detailed description of each instance variable defined by the
    class. </li> 
    <li> A detailed description of each class (static) variable defined
    by the class. </li> 
  </ul></p>

<h2> Project Documentation </h2>

  <p> The <b>Trees</b> page contains the module and class hierarchies:
  <ul>
    <li> The <i>module hierarchy</i> lists every package and module, with
    modules grouped into packages.  At the top level, and within each
    package, modules and sub-packages are listed alphabetically. </li>
    <li> The <i>class hierarchy</i> lists every class, grouped by base
    class.  If a class has more than one base class, then it will be
    listed under each base class.  At the top level, and under each base
    class, classes are listed alphabetically. </li>
  </ul></p>
  
  <p> The <b>Index</b> page contains indices of terms and
  identifiers: 
  <ul>
    <li> The <i>term index</i> lists every term indexed by any object's
    documentaiton.  For each term, the index provides links to each
    place where the term is indexed. </li>
    <li> The <i>identifier index</i> lists the (short) name of every package,
    module, class, method, function, variable, and parameter.  For each
    identifier, the index provides a short description, and a link to
    its documentation.  (<b>The identifier index is not implemented
    yet.</b>) </li>
  </ul></p>

<h2> The Navigation Bar </h2>

<p> A navigation bar is located at the top and bottom of every page.
It indicates what type of page you are currently viewing, and allows
you to go to related pages.  The following table describes the labels
on the navigation bar.  Note that not some labels (such as
[Parent]) are not displayed on all pages. </p>

<table class="summary" border="1" cellspacing="0" cellpadding="3" width="100%">
<tr class="summary">
  <th>Label</th>
  <th>Highlighted when...</th>
  <th>Links to...</th>
</tr>
  <tr><td valign="top"><b>[Parent]</b></td>
      <td valign="top"><i>(never highlighted)</i></td>
      <td valign="top"> the parent of the current package </td></tr>
  <tr><td valign="top"><b>[Package]</b></td>
      <td valign="top">viewing a package</td>
      <td valign="top">the package containing the current object
      </td></tr>
  <tr><td valign="top"><b>[Module]</b></td>
      <td valign="top">viewing a module</td>
      <td valign="top">the module containing the current object
      </td></tr> 
  <tr><td valign="top"><b>[Class]</b></td>
      <td valign="top">viewing a class </td>
      <td valign="top">the class containing the current object</td></tr>
  <tr><td valign="top"><b>[Trees]</b></td>
      <td valign="top">viewing the trees page</td>
      <td valign="top"> the trees page </td></tr>
  <tr><td valign="top"><b>[Index]</b></td>
      <td valign="top">viewing the index page</td>
      <td valign="top"> the index page </td></tr>
  <tr><td valign="top"><b>[Help]</b></td>
      <td valign="top">viewing the help page</td>
      <td valign="top"> the help page </td></tr>
</table>

<p> The "<b>show private</b>" and "<b>hide private</b>" buttons 
below the top navigation bar can be used to control whether
documentation for private objects is displayed.  Private objects are
defined as objects whose (short) names begin with a single underscore,
but do not end with an underscore.  For example, "<code>_x</code>",
"<code>__pprint</code>", and "<code>epydoc.epytext._tokenize</code>"
are private objects; but "<code>re.sub</code>",
"<code>__init__</code>", and "<code>type_</code>" are not. </p>

<p> A timestamp below the bottom navigation bar indicates when each
page was last updated. </p>
"""
