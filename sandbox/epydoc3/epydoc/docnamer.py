

"""

- Determine a unique (canonical) dotted name for every ValueDoc.

- Make sure that every ValueDoc is reachable from somewhere?
  - create an '<inaccessible>' ModuleDoc if necessary
  - rename to foo-2, foo-3 etc to avoid conflicts if necessary
  
- Populate a DocMap?

"""

def DocNamer:
    def __init__(self): pass
    
    def add_names(self, valuedocs):
        all_names = {}
        for valuedoc in valuedocs:
            self.find_all_names(valuedoc, all_names)

        for (valuedoc, names) in all_names.items():
            # Which name do we like best?
            

    def find_all_names(self, name, valuedoc, all_names, cyclecheck):
        pyid = id(valuedoc)

        # Don't go in circles.
        if cyclecheck.get(pyid): return
        cyclecheck[pyid] = True

        # Register the name choice, unless we already have a canonical
        # name for this ValueDoc.
        if valuedoc.dotted_name is None:
            all_names.setdefault(pyid, []).append(name)

        # Recurse to the VariableDoc children.
        for child in valuedoc.children():
            if (isinstance(child, VariableDoc) and
                child.valuedoc is not None):
                self.find_all_names(DottedName(name, child.name),
                                    child.valuedoc, all_names, cyclecheck)
                                        

                

    
