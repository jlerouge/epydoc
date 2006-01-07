# -*- coding: iso-8859-1 -*-
"""Module editordine
"""

# Copyright (C) 2005 by Daniele Varrazzo

# $Id$
__version__ = "$Revision$"[11:-2]

class EditOrdine:
    """Controllo per la modifica di un ordine.
            
    E' possibile specificare o l'id dell'ordine da modificare oppure passare un
    ordine - non entrambi! Se non ne viene passato nessuno, crea un nuovo
    ordine.
    
    :IVariables:
      * `sezione_id`: Id della sezione da cui è stato letto l'ordine, `None` se
        l'ordine è nuovo. Usato per verificare i permessi in caso di
        spostamento di sezione dell'ordine.
      * `importo`: Importo dell'ordine alla lettura, usato per verificare
        modifiche dell'importo. `None` se l'ordine è nuovo.
    """
