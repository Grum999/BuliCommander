from .bulicommander import BuliCommander

# And add the extension to Krita's list of extensions:
app = Krita.instance()
extension = BuliCommander(parent=app)
app.addExtension(extension)
