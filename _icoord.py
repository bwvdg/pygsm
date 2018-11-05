import numpy as np
import openbabel as ob
import pybel as pb
from units import *

'''
This file contains a ICoord class which is a Mixin for deloc_ic class
and it contains three slot classes which help with management of IC data
'''

class ICoords:

    def make_bonds(self):
        bonds=[]
        bondd=[]
        nbonds=0
        for bond in ob.OBMolBondIter(self.mol.OBMol):
            nbonds+=1
            a=bond.GetBeginAtomIdx()
            b=bond.GetEndAtomIdx()
            if a>b:
                bonds.append((a,b))
            else:
                bonds.append((b,a))

        bonds = sorted(bonds)
        for bond in bonds:
            bondd.append(self.distance(bond[0],bond[1]))
        return Bond_obj(nbonds,bonds,bondd)

    def make_angles(self):
        nangles=0
        angles=[]
        anglev=[]
        # openbabels iterator doesn't work because not updating properly
        for i,bond1 in enumerate(self.BObj.bonds):
            for bond2 in self.BObj.bonds[:i]:
                found=False
                if bond1[0] == bond2[0]:
                    angle = (bond1[1],bond1[0],bond2[1])
                    found=True
                elif bond1[0] == bond2[1]:
                    angle = (bond1[1],bond1[0],bond2[0])
                    found=True
                elif bond1[1] == bond2[0]:
                    angle = (bond1[0],bond1[1],bond2[1])
                    found=True
                elif bond1[1] == bond2[1]:
                    angle = (bond1[0],bond1[1],bond2[0])
                    found=True
                if found==True:
                    angv = self.get_angle(angle[0],angle[1],angle[2])
                    if angv>30.:
                        anglev.append(angv)
                        angles.append(angle)
                        nangles +=1

        print "number of angles is %i" %nangles
        print "printing angles"
        for angle,angv in zip(angles,anglev):
            print "%s %1.2f" %(angle,angv)
        return Ang_obj(nangles,angles,anglev)

    def make_torsions(self):
        ntor=0
        torsions=[]
        torv=[]
        # doesn't work because not updating properly
        for i,angle1 in enumerate(self.AObj.angles):
            for angle2 in self.AObj.angles[:i]:
                found = False
                a1=angle1[0]
                b1=angle1[1]
                c1=angle1[2]
                a2=angle2[0]
                b2=angle2[1]
                c2=angle2[2]
                if b1==c2 and b2==c1:
                    torsion = (a1,b1,b2,a2)
                    found = True
                elif b1==a2 and b2==c1:
                    torsion = (a1,b1,b2,c2)
                    found = True
                elif b1==c2 and b2==a1:
                    torsion = (c1,b1,b2,a2)
                    found = True
                elif b1==a2 and b2==a1:
                    torsion = (c1,b1,b2,c2)
                    found = True
                if found==True and (torsion[0] != torsion[2]) and torsion[0] != torsion[3] : 
                    ntor+=1
                    torsions.append(torsion)
                    t = self.get_torsion(torsion[0],torsion[1],torsion[2],torsion[3])
                    torv.append(t)

        print "number of torsions is %i" %ntor
        print "printing torsions"
        for n,torsion in enumerate(torsions):
            print "%s: %1.2f" %(torsion, torv[n])
        return Tor_obj(ntor,torsions,torv)



    def get_angle(self,i,j,k):
        a=self.mol.OBMol.GetAtom(i)
        b=self.mol.OBMol.GetAtom(j)
        c=self.mol.OBMol.GetAtom(k)
        return self.mol.OBMol.GetAngle(a,b,c) #b is the vertex #in degrees

    def get_torsion(self,i,j,k,l):
        a=self.mol.OBMol.GetAtom(i)
        b=self.mol.OBMol.GetAtom(j)
        c=self.mol.OBMol.GetAtom(k)
        d=self.mol.OBMol.GetAtom(l)
        tval=self.mol.OBMol.GetTorsion(a,b,c,d)*np.pi/180.
        #if tval >3.14159:
        if tval>=np.pi:
            tval-=2.*np.pi
        #if tval <-3.14159:
        if tval<=-np.pi:
            tval+=2.*np.pi
        return tval*180./np.pi

    def update_ic_eigen(self,gradq,nconstraints=0):
        SCALE =self.SCALEQN
        if self.newHess>0: SCALE = self.SCALEQN*self.newHess
        if self.SCALEQN>10.0: SCALE=10.0
        lambda1 = 0.0

        nicd_c = self.nicd-nconstraints
        temph = self.Hint[:nicd_c,:nicd_c]
        e,v_temp = np.linalg.eigh(temph)

        v = np.transpose(v_temp)
        leig = e[0]

        if leig < 0:
            lambda1 = -leig+0.015
        else:
            lambda1 = 0.005
        if abs(lambda1)<0.005: lambda1 = 0.005

        # => grad in eigenvector basis <= #
        gradq = gradq[:nicd_c,0]
        gqe = np.dot(v,gradq)

        dqe0 = np.divide(-gqe,e+lambda1)/SCALE
        dqe0 = [ np.sign(i)*self.MAXAD if abs(i)>self.MAXAD else i for i in dqe0 ]

        dq0 = np.dot(v_temp,dqe0)
        dq0 = [ np.sign(i)*self.MAXAD if abs(i)>self.MAXAD else i for i in dq0 ]
        #print "dq0"
        #print ["{0:0.5f}".format(i) for i in dq0]
        dq_c = np.zeros((self.nicd,1))
        for i in range(nicd_c):
            dq_c[i,0] = dq0[i]
        return dq_c

    def compute_predE(self,dq0):
        # compute predicted change in energy 
        assert np.shape(dq0)==(self.nicd,1), "dq0 not (nicd,1) "
        assert np.shape(self.gradq)==(self.nicd,1), "gradq not (nicd,1) "
        assert np.shape(self.Hint)==(self.nicd,self.nicd), "Hint not (nicd,nicd) "
        dEtemp = np.dot(self.Hint,dq0)
        dEpre = np.dot(np.transpose(dq0),self.gradq) + 0.5*np.dot(np.transpose(dEtemp),dq0)
        dEpre *=KCAL_MOL_PER_AU
        if abs(dEpre)<0.005: dEpre = np.sign(dEpre)*0.005
        print( "predE: %1.4f " % dEpre),
        return dEpre

    def grad_to_q(self,grad):
        gradq = np.dot(self.bmatti,grad)
        return gradq

    @staticmethod
    def tangent_1(ICoord1,ICoord2):
        ictan = []
        print "starting tangent 1"
        for bond1,bond2 in zip(ICoord1.BObj.bondd,ICoord2.BObj.bondd):
            ictan.append(bond1 - bond2)
        for angle1,angle2 in zip(ICoord1.AObj.anglev,ICoord2.AObj.anglev):
            ictan.append((angle1-angle2)*np.pi/180.)
        for torsion1,torsion2 in zip(ICoord1.TObj.torv,ICoord2.TObj.torv):
            temptorsion = (torsion1-torsion2)*np.pi/180.0
            if temptorsion > np.pi:
                ictan.append(-1*((2*np.pi) - temptorsion))
            elif temptorsion < -np.pi:
                ictan.append((2*np.pi)+temptorsion)
            else:
                ictan.append(temptorsion)
        print 'ending tangent 1'
        print "printing ictan"
        for i in range(ICoord1.BObj.nbonds):
            print "%1.2f " %ictan[i],
        for i in range(ICoord1.BObj.nbonds,ICoord1.AObj.nangles+ICoord1.BObj.nbonds):
            print "%1.2f " %ictan[i],
        for i in range(ICoord1.BObj.nbonds+ICoord1.AObj.nangles,ICoord1.AObj.nangles+ICoord1.BObj.nbonds+ICoord1.TObj.ntor):
            print "%1.2f " %ictan[i],
        print "\n"
        return np.asarray(ictan).reshape((ICoord1.num_ics,1))






######################  IC objects #####################################
class Bond_obj(object):
    __slots__ = ["nbonds","bonds","bondd"]
    def __init__(self,nbonds,bonds,bondd):
        self.nbonds=nbonds
        self.bonds=bonds
        self.bondd=bondd

    def update(self,mol):
        self.bondd=[]
        self.nbonds = len(self.bonds)
        for bond in self.bonds:
            self.bondd.append(self.distance(mol,bond[0],bond[1]))

    def distance(self,mol,i,j):
        """ for some reason openbabel has this one based """
        a1=mol.OBMol.GetAtom(i)
        a2=mol.OBMol.GetAtom(j)
        return a1.GetDistance(a2)

class Ang_obj(object):
    __slots__ = ["nangles","angles","anglev"]
    def __init__(self,nangles,angles,anglev):
        self.nangles=nangles
        self.angles=angles
        self.anglev=anglev

    def update(self,mol):
        self.anglev=[]
        self.nangles = len(self.angles)
        for angle in self.angles:
            self.anglev.append(self.get_angle(mol,angle[0],angle[1],angle[2]))

    def get_angle(self,mol,i,j,k):
        a=mol.OBMol.GetAtom(i)
        b=mol.OBMol.GetAtom(j)
        c=mol.OBMol.GetAtom(k)
        return mol.OBMol.GetAngle(a,b,c) #b is the vertex #in degrees


class Tor_obj(object):
    __slots__ = ["ntor","torsions","torv"]
    def __init__(self,ntor,torsions,torv):
        self.ntor=ntor
        self.torsions=torsions
        self.torv=torv

    def update(self,mol):
        self.torv=[]
        self.ntor = len(self.torsions)
        for torsion in self.torsions:
            self.torv.append(self.get_torsion(mol,torsion[0],torsion[1],torsion[2],torsion[3]))

    def get_torsion(self,mol,i,j,k,l):
        a=mol.OBMol.GetAtom(i)
        b=mol.OBMol.GetAtom(j)
        c=mol.OBMol.GetAtom(k)
        d=mol.OBMol.GetAtom(l)
        tval=mol.OBMol.GetTorsion(a,b,c,d)*np.pi/180.
        if tval>=np.pi:
            tval-=2.*np.pi
        if tval<=-np.pi:
            tval+=2.*np.pi
        return tval*180./np.pi



    """
    def make_imptor(self):
        self.imptor=[]
        self.nimptor=0
        self.imptorv=[]
        count=0
        for i in self.AObj.angles:
            #print i
            try:
                for j in self.AObj.angles[0:count]:
                    found=False
                    a1=i[0]
                    m1=i[1]
                    c1=i[2]
                    a2=j[0]
                    m2=j[1]
                    c2=j[2]
                    #print(" angle: %i %i %i angle2: %i %i %i" % (a1,m1,c1,a2,m2,c2))
                    if m1==m2:
                        if a1==a2:
                            found=True
                            d=self.mol.OBMol.GetAtom(c2+1)
                        elif a1==c2:
                            found=True
                            d=self.mol.OBMol.GetAtom(a2+1)
                        elif c1==c2:
                            found=True
                            d=self.mol.OBMol.GetAtom(a2+1)
                        elif c1==a2:
                            found=True
                            d=self.mol.OBMol.GetAtom(c2+1)
                    if found==True:
                        a=self.mol.OBMol.GetAtom(c1+1)
                        b=self.mol.OBMol.GetAtom(a1+1)
                        c=self.mol.OBMol.GetAtom(m1+1)
                        imptorvt=self.mol.OBMol.GetTorsion(a,b,c,d)
                        #print imptorvt
                        if abs(imptorvt)>12.0 and abs(imptorvt-180.)>12.0:
                            found=False
                        else:
                            self.imptorv.append(imptorvt)
                            self.imptor.append((a.GetIndex(),b.GetIndex(),c.GetIndex(),d.GetIndex()))
                            self.nimptor+=1
            except Exception as e: print(e)
            count+=1
            return

    def make_nonbond(self):
        self.nonbond=[]
        for i in range(self.natoms):
            for j in range(i):
                found=False
                for k in range(self.BObj.nbonds):
                    if found==True:
                        break
                    if (self.BObj.bonds[k][0]==i and self.BObj.bonds[k][1]==j) or (self.BObj.bonds[k][0]==j and self.BObj.bonds[k][1]==i):
                        found=True
                for k in range(self.AObj.nangles):
                    if found==True:
                        break
                    if self.AObj.angles[k][0]==i:
                        if self.AObj.angles[k][1]==j:
                            found=True
                        elif self.AObj.angles[k][2]==j:
                            found=True
                    elif self.AObj.angles[k][1]==i:
                        if self.AObj.angles[k][0]==j:
                            found=True
                        elif self.AObj.angles[k][2]==j:
                            found=True
                    elif self.AObj.angles[k][2]==i:
                        if self.AObj.angles[k][0]==j:
                            found=True
                        elif self.AObj.angles[k][1]==j:
                            found=True
                if found==False:
                   self.nonbond.append(self.distance(i,j))
        #print self.nonbond

    """
