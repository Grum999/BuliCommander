from .kritacommander import KritaCommander

# And add the extension to Krita's list of extensions:
app = Krita.instance()
# Instantiate your class:
extension = KritaCommander(parent=app)
app.addExtension(extension)
