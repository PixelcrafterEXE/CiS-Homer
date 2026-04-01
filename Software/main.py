from lib.UI import UI
from lib.Sensor import Sensor

def main():
    #ui = UI()
    #ui.mainloop()
    S = Sensor()
    S.writeGain(1)
    print(S.getGain())

if __name__ == "__main__":
    main()