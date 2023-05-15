(ns jepsen.etcdemo
  (:require [clojure.tools.logging :refer :all]
            [clojure.string :as str]
            [knossos
                    [model :as model]
                    [competition :as competition]]
            [jepsen 
                    [checker :as checker]
                    [cli :as cli]
                    [control :as c]
                    [db :as db]
                    [tests :as tests]
                    [client :as client]
                    [generator :as gen]
                    [tests :as tests]
                    ]
            [jepsen.control.util :as cu]
            [jepsen.os.debian :as debian]))
(import (java.net Socket))
(import (java.io DataInputStream DataOutputStream))
(import (java.io BufferedInputStream BufferedInputStream))
(import (java.io BufferedOutputStream BufferedOutputStream))
(import (java.nio ByteBuffer ByteBuffer))
(import (java.nio ByteOrder ByteOrder))
(require '[clojure.string :as str])
(require '[clojure.pprint])

(def dir     "/tmp/ecm")
(def binary "/usr/bin/python3")
(def logfile (str dir "/ecm.log"))
(def pidfile (str dir "/ecm.pid"))

(defn r   [_ _] {:type :invoke, :f :read, :value nil})
(defn w   [_ _] {:type :invoke, :f :write, :value (rand-int 5)})
(defn cas [_ _] {:type :invoke, :f :cas, :value [(rand-int 5) (rand-int 5)]})

(defn db
  "eventually-consistent-mesh DB for a particular version."
  [version]
  (reify db/DB
    (setup! [_ test node]
      (info node "installing eventually-consistent-mesh" version)
      (c/su 
        (c/exec ["pkill", "-f", "python3"]))
      (c/exec ["sudo", "apt-get", "update"])
      (c/exec ["sudo", "apt-get", "install", "graphviz", "-y"])
      (c/exec ["sudo", "rm", "-rf", "/tmp/ecm"])
      (c/exec ["mkdir", "-p", "/tmp/ecm"])
      (c/exec ["mkdir", "-p", "/tmp/ecm/logs"])
      (c/exec ["mkdir", "-p", "/tmp/ecm/diagrams"])
      (c/upload "../node_cluster.py" "/tmp/ecm")
      (c/upload "nodes" "/tmp/ecm")
      (c/su
      (cu/start-daemon!
          {:logfile logfile
           :chdir   dir
           :background? true}
       binary  
       :node_cluster.py
       :run
       :--index
       node
       :--nodes-file
       :nodes))
       (Thread/sleep 5000))
    

    (teardown! [_ test node]
      (info node "tearing down eventually-consistent-mesh")
       (cu/stop-daemon! binary pidfile)
       (c/su 
        (c/exec ["pkill", "-f", "python3"])))

    db/LogFiles
        (log-files [_ test node]
          [logfile])))


(defrecord Client [conn]
  client/Client
  (open! [this test node]
  (let [node_data (slurp "nodes") 
     lines (str/split node_data #"\n") 
     index (loop [i 0]
      (let [inext (+ i 1)]
        (if (= (nth lines i) node)
           i
          (if (< i (count lines))
            (recur inext)
            -1)
            ))) ]
        (def port (+ 65432 index))
        (def command "server clientonly\t")
        (def IPaddress node)
          (->> 
            #(try
              (let [size (ByteBuffer/allocate Long/BYTES)
                   socket (Socket. IPaddress port)
                   out (BufferedOutputStream. (.getOutputStream socket))
                   in (BufferedInputStream. (.getInputStream socket))
                ]
            
              (.println *err* (str "Connecting to server " node " on port " port))
              (.order size ByteOrder/BIG_ENDIAN)
              (.rewind size) 
              (comment (.println *err* (str (.isConnected socket))))
              (.println *err* (str size))
              (.putLong size 0 (count command))
               
              (.println *err* (str "size of array is " (count (.array size))))
              (.write out (.array size) 0 8)
              (.write out (.getBytes command) 0 (count (.getBytes command)))
              (.flush out)
              (comment (def response (.readUTF in)))
              (println "Output: " command)
              (Thread/sleep 250)
              (assoc this :conn socket :out out :in in)
             )
         (catch Exception e
          (.println *err* (str e))
          (Thread/sleep 500)
          nil 
         ))
         (repeatedly 5) 
         (some identity)
          )
        
        
        )
      ) 

  (setup! [this test])

  (invoke! [this test op]
      (case (:f op)
        :write (do 
                (let [size (ByteBuffer/allocate Long/BYTES)
                    responseSize (ByteBuffer/allocate 100) 
                    in (:in this)
                    out (:out this)
                    command (str "set " (rand-nth ["withdraw" "deposit"]) " balance " (:value op) " " (System/nanoTime) "\t") ]
                  (.order responseSize ByteOrder/BIG_ENDIAN)
                  (.order size ByteOrder/BIG_ENDIAN)
                  (.putLong size 0 (count command))
                  (.write out (.array size) 0 8)
                  (.write out (.getBytes command) 0 (count (.getBytes command)))
                  (.flush out)
                  (.println *err* (str "Writing to server which is " (:value op)))
                  (.println *err* (str command))
                  (comment (def response (.read in (.array responseSize) 8 0)))
                  (comment (println "Output: " response))
                  (assoc op :type :ok)
                   
            ))
        :read (assoc op :type :ok, :value 

                (let [size (ByteBuffer/allocate Long/BYTES)
                    responseSize (ByteBuffer/allocate 100) 
                    in (:in this)
                    out (:out this)
                    command (str "get balance " (System/nanoTime) "\t") ]
                  (.order responseSize ByteOrder/BIG_ENDIAN)
                  (.order size ByteOrder/BIG_ENDIAN)
                  (.putLong size 0 (count command))
                  (.write out (.array size) 0 8)
                  (.write out (.getBytes command) 0 (count (.getBytes command)))
                  (.flush out)
                  (comment (def response (.read in (.array responseSize) 8 0)))
                  (comment (println "Output: " response))
                  (let [response (.read in (.array responseSize) 0 8)
                        serverValue (.getLong responseSize)]
                    (.println *err* (str "Received LONG from server which is " serverValue ))
                    serverValue
                  )
              
            )
    ))

  )

  (teardown! [this test])

  (close! [this test]
  (.println *err* (str this))
  (.close (:conn this))
  )
)
(defn ecm-test
  "Given an options map from the command line runner (e.g. :nodes, :ssh,
  :concurrency, ...), constructs a test map."
  [opts]
  (merge tests/noop-test
         opts
         {:pure-generators true
          :db (db "1")
          :client (Client. nil)
          :checker (checker/linearizable
                              {:model     (model/cas-register)
                              :algorithm :linear})
          :generator       (->> (gen/mix [r w])
                                (gen/stagger 1)
                                (gen/nemesis nil)
                                (gen/time-limit 15))
         }
         ))

(defn -main
  "Handles command line arguments. Can either run a test, or a web server for
  browsing results."
  [& args]
  (cli/run! (cli/single-test-cmd {:test-fn ecm-test})
            args))

