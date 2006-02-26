# epydoc -- API documentation inheritance
#
# Copyright (C) 2005 Edward Loper
# Author: Edward Loper <edloper@loper.org>
# URL: <http://epydoc.sf.net>
#
# $Id$

from epydoc.apidoc import *

# [XX] should we add the new variables to the docindex?? hm..  But
# then this wouldn't just be direct children, could potentailly be
# lots and lots of stuff..

# [xx] should inheriting make new variables, or copy the var_doc
# objects??  probably make new ones?
class DocInheriter:

    def inherit(self, docindex):
        for val_doc in docindex.reachable_valdocs:
            # Do inheritance
            if isinstance(val_doc, ClassDoc):
                self._inherit(val_doc)

            # Sorting & grouping of variables in namespaces.
            if isinstance(val_doc, NamespaceDoc):
                self.init_sorted_variables(val_doc)
                self.init_groups(val_doc)

            ## While we're at it, publicify!
            #if isinstance(val_doc, NamespaceDoc):
            #    if val_doc.public_names
            #    for var in 
        
                
    def _inherit(self, class_doc):
        class_doc.variables = class_doc.local_variables.copy()
        
        mro = list(class_doc.mro())
        
        for cls in mro:
            if cls == class_doc: continue
            if cls.local_variables is UNKNOWN: continue
            
            for name, var_doc in cls.local_variables.items():
                if name not in class_doc.variables:
                    # Inherit this variable.
                    self._inherit_var(class_doc, name, var_doc)
                else:
                    # Record the fact that we override this variable.
                    if class_doc.variables[name].overrides is UNKNOWN:
                        class_doc.variables[name].overrides = var_doc
                        self._inherit_info(class_doc.variables[name])

    def _inherit_var(self, dst_class, name, src_var):
        dst_var = VariableDoc(**src_var.__dict__)
        # [xx] keep pointer to *original* container?
        #dst_var.container = src_var.container
        dst_var.is_inherited = True
        dst_class.variables[name] = dst_var

    def _inherit_info(self, var_doc):
        """
        Inherit..
          - descr
          - summary
          - metadata??
          - param descrs & types?
          
        """
        # [XX] flesh this out!
        if var_doc.descr in (None, UNKNOWN):
            var_doc.descr = var_doc.overrides.descr
        if (var_doc.value not in (None, UNKNOWN) and
            var_doc.value.descr in (None, UNKNOWN)):
            var_doc.value.descr = var_doc.overrides.value.descr



    #////////////////////////////////////////////////////////////
    # Group & sort!
    #////////////////////////////////////////////////////////////

    def init_sorted_variables(self, api_doc):
        unsorted = api_doc.variables.copy()
        api_doc.sorted_variables = []

        # Add any variables that are listed in sort_spec
        if api_doc.sort_spec is not UNKNOWN:
            for ident in api_doc.sort_spec:
                var_doc = unsorted.pop(ident, None)
                if var_doc is not None:
                    api_doc.sorted_variables.append(var_doc)
                elif '*' in ident:
                    regexp = re.compile('^%s$' % ident.replace('*', '(.*)'))
                    # sort within matching group?
                    for name, var_doc in unsorted.items():
                        if regexp.match(name):
                            api_doc.sorted_variables.append(var_doc)
                            unsorted.remove(var_doc)

        # Add any remaining variables in alphabetical order.
        var_docs = unsorted.items()
        var_docs.sort()
        for name, var_doc in var_docs:
            api_doc.sorted_variables.append(var_doc)

    def init_groups(self, api_doc):
        assert len(api_doc.sorted_variables) == len(api_doc.variables)
        
        api_doc.group_names = [''] + [n for (n,vs) in api_doc.group_specs]
        api_doc.groups = {}
        
        # Make the common case fast:
        if len(api_doc.group_names) == 1:
            api_doc.groups[''] = api_doc.sorted_variables
            return

        for group in api_doc.group_names:
            api_doc.groups[group] = []

        # Create a mapping from elt -> group name.
        varname2groupname = {}
        regexp_groups = []

        for group_name, var_names in api_doc.group_specs:
            for var_name in var_names:
                if '*' not in var_name:
                    varname2groupname[var_name] = group_name
                else:
                    var_name_re = '^%s$' % var_name.replace('*', '(.*)')
                    var_name_re = re.compile(var_name_re)
                    regexp_groups.append( (group_name, var_name_re) )

        # Use the elt -> group name mapping to put each elt in the
        # right group.
        for var_doc in api_doc.sorted_variables:
            group_name = varname2groupname.get(var_doc.name, '')
            api_doc.groups[group_name].append(var_doc)

        # Handle any regexp groups, by moving elements from the
        # ungrouped list to the appropriate group.
        ungrouped = api_doc.groups['']
        for (group_name, regexp) in regexp_groups:
            for i in range(len(ungrouped)-1, -1, -1):
                elt = ungrouped[i]
                if regexp.match(elt.name):
                    api_doc.groups[group_name].append(elt)
                    del ungrouped[i]

        # [xx] check for empty groups???

        
        

        
